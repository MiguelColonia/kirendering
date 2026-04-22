"""Endpoints para lanzar, listar y descargar imágenes de difusión."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from cimiento.api.dependencies import get_job_manager, get_repository
from cimiento.api.errors import api_error, diffusion_not_found, project_not_found
from cimiento.api.i18n import translate_error
from cimiento.api.jobs import JobManager
from cimiento.api.schemas import (
    DiffusionCreateRequest,
    DiffusionGalleryItemResponse,
    JobStartResponse,
)
from cimiento.diffusion import run_diffusion
from cimiento.persistence.models import GeneratedOutput, ProjectVersion
from cimiento.persistence.repository import ProjectRepository
from cimiento.schemas.diffusion import DiffusionConfig, DiffusionMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["diffusion"])

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def _diffusion_urls(diffusion_id: str) -> tuple[str, str]:
    image_url = f"/api/diffusion/{diffusion_id}"
    return image_url, f"{image_url}?download=1"


def _serialize_diffusion(
    project_id: str,
    version: ProjectVersion,
    output: GeneratedOutput,
) -> DiffusionGalleryItemResponse:
    metadata = output.output_metadata or {}
    image_url, download_url = _diffusion_urls(output.id)
    return DiffusionGalleryItemResponse(
        id=output.id,
        project_id=project_id,
        version_id=version.id,
        version_number=version.version_number,
        mode=str(metadata.get("mode", "unknown")),
        prompt=metadata.get("prompt"),
        image_url=image_url,
        download_url=download_url,
        media_type=output.media_type,
        created_at=output.created_at,
        duration_seconds=metadata.get("duration_seconds"),
        device_used=metadata.get("device_used"),
        warnings=metadata.get("warnings", []),
    )


async def _run_diffusion_job(
    app: object,
    job_id: str,
    project_id: str,
    version_id: str,
    input_image_path: Path,
    payload: DiffusionCreateRequest,
) -> None:
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
    repository = ProjectRepository(app.state.session_factory)
    job_manager: JobManager = app.state.job_manager
    output_root: Path = app.state.output_root
    settings = app.state.settings

    try:
        version = await repository.get_project_version(version_id)
        if version is None:
            await job_manager.fail(
                job_id,
                code="PROJECT_HAS_NO_VERSION",
                message=translate_error("PROJECT_HAS_NO_VERSION"),
            )
            return

        output_dir = output_root / project_id / f"v{version.version_number}" / "diffusion" / job_id

        await job_manager.publish(
            job_id,
            "diffusion_started",
            status="running",
            data={"mode": payload.mode.value},
        )

        diffusion_result = await asyncio.to_thread(
            run_diffusion,
            DiffusionConfig(
                project_id=project_id,
                mode=payload.mode,
                input_image_path=input_image_path,
                output_dir=output_dir,
                prompt=payload.prompt,
                negative_prompt=payload.negative_prompt,
                num_inference_steps=settings.diffusion_steps,
                guidance_scale=payload.guidance_scale,
                image_guidance_scale=payload.image_guidance_scale,
                controlnet_conditioning_scale=payload.controlnet_conditioning_scale,
                seed=payload.seed,
                timeout_seconds=settings.diffusion_timeout_seconds,
            ),
            settings=settings,
        )

        diffusion_output = await repository.create_generated_output(
            version_id,
            output_type="DIFFUSION",
            file_path=str(diffusion_result.output_path),
            media_type="image/png",
            output_metadata={
                "mode": diffusion_result.mode.value,
                "prompt": payload.prompt,
                "negative_prompt": payload.negative_prompt,
                "duration_seconds": diffusion_result.duration_seconds,
                "device_used": diffusion_result.device_used,
                "width": diffusion_result.width,
                "height": diffusion_result.height,
                "warnings": diffusion_result.warnings,
            },
        )

        await job_manager.publish(
            job_id,
            "diffusion_finished",
            data={
                "diffusion_id": diffusion_output.id,
                "mode": diffusion_result.mode.value,
                "duration_seconds": diffusion_result.duration_seconds,
            },
        )
        await job_manager.finish(job_id, output_formats=["diffusion"])

    except Exception:  # noqa: BLE001
        logger.exception("Fallo inesperado durante la difusión del proyecto '%s'", project_id)
        await job_manager.fail(
            job_id,
            code="DIFFUSION_FAILED",
            message=translate_error("DIFFUSION_FAILED"),
        )


@router.post(
    "/projects/{project_id}/diffusion",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStartResponse,
)
async def create_diffusion(
    project_id: str,
    mode: str,
    prompt: str,
    file: UploadFile,
    request: Request,
    negative_prompt: str = "",
    guidance_scale: float = 7.5,
    image_guidance_scale: float = 1.5,
    controlnet_conditioning_scale: float = 1.0,
    seed: int | None = None,
    repository: ProjectRepository = Depends(get_repository),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobStartResponse:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    version = await repository.get_latest_project_version(project_id)
    if version is None:
        raise api_error(status.HTTP_409_CONFLICT, "PROJECT_HAS_NO_VERSION", project_id=project_id)

    try:
        diffusion_mode = DiffusionMode(mode)
    except ValueError:
        raise api_error(status.HTTP_400_BAD_REQUEST, "DIFFUSION_INPUT_MISSING")  # noqa: B904

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_PLAN_IMAGE")

    output_root: Path = request.app.state.output_root
    input_dir = output_root / project_id / "diffusion_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    job = job_manager.create_job(project_id=project_id, version_id=version.id)
    input_path = input_dir / f"{job.id}_{file.filename}"
    content = await file.read()
    input_path.write_bytes(content)

    payload = DiffusionCreateRequest(
        mode=diffusion_mode,
        prompt=prompt,
        negative_prompt=negative_prompt,
        guidance_scale=guidance_scale,
        image_guidance_scale=image_guidance_scale,
        controlnet_conditioning_scale=controlnet_conditioning_scale,
        seed=seed,
    )

    task = asyncio.create_task(
        _run_diffusion_job(
            request.app,
            job.id,
            project_id,
            version.id,
            input_path,
            payload,
        )
    )
    job_manager.set_task(job.id, task)
    logger.info("Iniciando job de difusión '%s' para el proyecto '%s'", mode, project_id)
    return JobStartResponse(job_id=job.id, status=job.status, project_id=project_id)


@router.get(
    "/projects/{project_id}/diffusion",
    response_model=list[DiffusionGalleryItemResponse],
)
async def list_diffusion(
    project_id: str,
    repository: ProjectRepository = Depends(get_repository),
) -> list[DiffusionGalleryItemResponse]:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    versions = await repository.list_project_versions(project_id)
    items = [
        _serialize_diffusion(project_id, version, output)
        for version in versions
        for output in version.generated_outputs
        if output.output_type == "DIFFUSION"
    ]
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items


@router.get("/diffusion/{diffusion_id}")
async def get_diffusion(
    diffusion_id: str,
    download: bool = Query(False),
    repository: ProjectRepository = Depends(get_repository),
) -> FileResponse:
    output = await repository.get_generated_output(diffusion_id)
    if output is None or output.output_type != "DIFFUSION":
        raise diffusion_not_found(diffusion_id)

    file_path = Path(output.file_path)
    if not file_path.exists():
        raise diffusion_not_found(diffusion_id)

    filename = file_path.name if not download else f"diffusion-{diffusion_id}{file_path.suffix}"
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=output.media_type or "image/png",
        content_disposition_type="attachment" if download else "inline",
    )
