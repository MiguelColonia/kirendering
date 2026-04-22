"""Endpoints para crear, listar y descargar renders de proyecto."""

from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from fastapi.responses import FileResponse

from cimiento.api.dependencies import get_job_manager, get_repository
from cimiento.api.errors import api_error, project_not_found, render_not_found
from cimiento.api.i18n import translate_error
from cimiento.api.jobs import JobManager
from cimiento.api.schemas import JobStartResponse, RenderCreateRequest, RenderGalleryItemResponse
from cimiento.persistence.models import GeneratedOutput, ProjectVersion
from cimiento.persistence.repository import ProjectRepository
from cimiento.render import run_render
from cimiento.schemas.render import RenderConfig, RenderView

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["renders"])

RenderViewType = Literal["exterior", "interior"]
_REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _estimate_render_duration_seconds(
    *,
    width: int,
    height: int,
    samples: int,
    requested_view: RenderViewType,
) -> int:
    megapixels = (width * height) / 1_000_000
    sample_factor = samples / 64
    view_factor = 1.0 if requested_view == "exterior" else 1.15
    estimated = 18 + (megapixels * 38 * sample_factor * view_factor)
    return max(30, int(round(estimated)))


def _select_render_view(
    views: Sequence[RenderView],
    requested_view: RenderViewType,
) -> RenderView | None:
    preferred_prefixes = ("exterior_", "aerial") if requested_view == "exterior" else ("interior_",)
    for prefix in preferred_prefixes:
        for view in views:
            if view.name.startswith(prefix):
                return view
    return views[0] if views else None


def _render_urls(render_id: str) -> tuple[str, str]:
    image_url = f"/api/renders/{render_id}"
    return image_url, f"{image_url}?download=1"


def _serialize_render(
    project_id: str,
    version: ProjectVersion,
    output: GeneratedOutput,
) -> RenderGalleryItemResponse:
    metadata = output.output_metadata or {}
    image_url, download_url = _render_urls(output.id)
    return RenderGalleryItemResponse(
        id=output.id,
        project_id=project_id,
        version_id=version.id,
        version_number=version.version_number,
        view=str(metadata.get("view", "exterior")),
        prompt=metadata.get("prompt"),
        image_url=image_url,
        download_url=download_url,
        media_type=output.media_type,
        created_at=output.created_at,
        has_reference_image=bool(metadata.get("reference_image_name")),
        reference_image_name=metadata.get("reference_image_name"),
        duration_seconds=metadata.get("duration_seconds"),
        estimated_total_seconds=metadata.get("estimated_total_seconds"),
        device_used=metadata.get("device_used"),
    )


async def _save_reference_image(
    output_root: Path,
    project_id: str,
    job_id: str,
    reference_image_name: str,
    reference_image_base64: str,
    reference_image_media_type: str | None,
) -> tuple[Path, str]:
    filename = Path(reference_image_name).name
    suffix = Path(filename).suffix.lower()
    content_type = reference_image_media_type or ""
    if suffix not in _REFERENCE_EXTENSIONS:
        raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_REFERENCE_IMAGE")
    if content_type and not content_type.startswith("image/"):
        raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_REFERENCE_IMAGE")

    payload = (
        reference_image_base64.split(",", 1)[1]
        if reference_image_base64.startswith("data:")
        else reference_image_base64
    )
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except ValueError as exc:
        raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_REFERENCE_IMAGE") from exc

    reference_dir = output_root / project_id / "references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    target_path = reference_dir / f"{job_id}-{filename}"
    target_path.write_bytes(image_bytes)
    return target_path, filename


async def _run_render_job(
    app: FastAPI,
    job_id: str,
    project_id: str,
    version_id: str,
    requested_view: RenderViewType,
    prompt: str | None,
    reference_image_path: Path | None,
    reference_image_name: str | None,
) -> None:
    repository = ProjectRepository(app.state.session_factory)
    job_manager: JobManager = app.state.job_manager
    output_root: Path = app.state.output_root
    settings = app.state.settings

    estimated_total_seconds = _estimate_render_duration_seconds(
        width=settings.render_width,
        height=settings.render_height,
        samples=settings.render_samples,
        requested_view=requested_view,
    )

    try:
        version = await repository.get_project_version(version_id)
        if version is None:
            await job_manager.fail(
                job_id,
                code="PROJECT_HAS_NO_VERSION",
                message=translate_error("PROJECT_HAS_NO_VERSION"),
            )
            return

        solar = version.get_solar_model()
        ifc_output = await repository.get_latest_generated_output(version_id, "IFC")
        if ifc_output is None:
            await job_manager.fail(
                job_id,
                code="PROJECT_HAS_NO_IFC",
                message=translate_error("PROJECT_HAS_NO_IFC"),
            )
            return

        ifc_path = Path(ifc_output.file_path)
        if not ifc_path.exists():
            await job_manager.fail(
                job_id,
                code="PROJECT_HAS_NO_IFC",
                message=translate_error("PROJECT_HAS_NO_IFC"),
            )
            return

        render_output_dir = (
            output_root / project_id / f"v{version.version_number}" / "renders" / job_id
        )
        render_output_dir.mkdir(parents=True, exist_ok=True)

        await job_manager.publish(
            job_id,
            "render_started",
            status="running",
            data={
                "view": requested_view,
                "estimated_total_seconds": estimated_total_seconds,
                "has_reference_image": reference_image_name is not None,
            },
        )

        render_result = await asyncio.to_thread(
            run_render,
            RenderConfig(
                ifc_path=ifc_path,
                project_id=project_id,
                output_dir=render_output_dir,
                north_angle_deg=solar.north_angle_deg,
                render_width=settings.render_width,
                render_height=settings.render_height,
                samples=settings.render_samples,
                blender_executable=Path(settings.blender_executable),
                timeout_seconds=settings.render_timeout_seconds,
            ),
        )

        selected_view = _select_render_view(render_result.views, requested_view)
        if selected_view is None or not selected_view.output_path.exists():
            await job_manager.fail(
                job_id,
                code="RENDER_VIEW_NOT_AVAILABLE",
                message=translate_error("RENDER_VIEW_NOT_AVAILABLE"),
            )
            return

        render_output = await repository.create_generated_output(
            version_id,
            output_type="RENDER",
            file_path=str(selected_view.output_path),
            media_type="image/png",
            output_metadata={
                "view": requested_view,
                "prompt": prompt,
                "reference_image_path": str(reference_image_path) if reference_image_path else None,
                "reference_image_name": reference_image_name,
                "selected_view_name": selected_view.name,
                "available_views": [view.name for view in render_result.views],
                "duration_seconds": selected_view.duration_seconds,
                "total_duration_seconds": render_result.total_duration_seconds,
                "estimated_total_seconds": estimated_total_seconds,
                "device_used": render_result.device_used,
                "blender_version": render_result.blender_version,
            },
        )

        await job_manager.publish(
            job_id,
            "render_finished",
            data={
                "render_id": render_output.id,
                "view": requested_view,
                "duration_seconds": selected_view.duration_seconds,
            },
        )
        await job_manager.finish(job_id, output_formats=["render"])
    except Exception:  # noqa: BLE001
        logger.exception("Fallo inesperado durante el render del proyecto '%s'", project_id)
        await job_manager.fail(
            job_id,
            code="RENDER_FAILED",
            message=translate_error("RENDER_FAILED"),
        )


@router.post(
    "/projects/{project_id}/renders",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStartResponse,
)
async def create_render(
    project_id: str,
    payload: RenderCreateRequest,
    request: Request,
    repository: ProjectRepository = Depends(get_repository),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobStartResponse:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    version = await repository.get_latest_project_version(project_id)
    if version is None:
        raise api_error(status.HTTP_409_CONFLICT, "PROJECT_HAS_NO_VERSION", project_id=project_id)

    ifc_output = await repository.get_latest_generated_output(version.id, "IFC")
    if ifc_output is None or not Path(ifc_output.file_path).exists():
        raise api_error(status.HTTP_409_CONFLICT, "PROJECT_HAS_NO_IFC", project_id=project_id)

    logger.info("Iniciando job de render para el proyecto '%s'", project_id)
    job = job_manager.create_job(project_id=project_id, version_id=version.id)

    reference_image_path: Path | None = None
    reference_image_name: str | None = None
    if payload.reference_image_base64 is not None:
        if payload.reference_image_name is None:
            raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_REFERENCE_IMAGE")
        reference_image_path, reference_image_name = await _save_reference_image(
            request.app.state.output_root,
            project_id,
            job.id,
            payload.reference_image_name,
            payload.reference_image_base64,
            payload.reference_image_media_type,
        )

    task = asyncio.create_task(
        _run_render_job(
            request.app,
            job.id,
            project_id,
            version.id,
            payload.view,
            payload.prompt.strip() if payload.prompt else None,
            reference_image_path,
            reference_image_name,
        )
    )
    job_manager.set_task(job.id, task)
    return JobStartResponse(job_id=job.id, status=job.status, project_id=project_id)


@router.get("/projects/{project_id}/renders", response_model=list[RenderGalleryItemResponse])
async def list_renders(
    project_id: str,
    repository: ProjectRepository = Depends(get_repository),
) -> list[RenderGalleryItemResponse]:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    versions = await repository.list_project_versions(project_id)
    renders = [
        _serialize_render(project_id, version, output)
        for version in versions
        for output in version.generated_outputs
        if output.output_type == "RENDER"
    ]
    renders.sort(key=lambda render: render.created_at, reverse=True)
    return renders


@router.get("/renders/{render_id}")
async def get_render(
    render_id: str,
    download: bool = Query(False),
    repository: ProjectRepository = Depends(get_repository),
) -> FileResponse:
    render = await repository.get_generated_output(render_id)
    if render is None or render.output_type != "RENDER":
        raise render_not_found(render_id)

    file_path = Path(render.file_path)
    if not file_path.exists():
        raise render_not_found(render_id)

    filename = file_path.name if not download else f"render-{render_id}{file_path.suffix}"
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=render.media_type or "application/octet-stream",
        content_disposition_type="attachment" if download else "inline",
    )
