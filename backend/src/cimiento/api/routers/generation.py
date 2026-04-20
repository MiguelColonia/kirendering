"""Endpoints para generar soluciones y seguir su progreso por job."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, status

from cimiento.api.dependencies import get_job_manager, get_output_root, get_repository
from cimiento.api.errors import api_error, job_not_found, project_not_found
from cimiento.api.i18n import translate_error
from cimiento.api.jobs import JobManager
from cimiento.api.schemas import JobErrorResponse, JobEventResponse, JobStartResponse, JobStatusResponse
from cimiento.bim import export_to_dxf, export_to_ifc, export_to_xlsx
from cimiento.geometry import build_building_from_solution
from cimiento.persistence.repository import ProjectRepository
from cimiento.schemas import Program, Solar, SolutionStatus
from cimiento.solver import solve

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generation"])


def _draw_svg(solar: Solar, solution, output_path: Path) -> None:
    pts = solar.contour.points
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = 10.0
    pad = 20
    width = (max_x - min_x) * scale + 2 * pad
    height = (max_y - min_y) * scale + 2 * pad

    def tx(x: float) -> float:
        return (x - min_x) * scale + pad

    def ty(y: float) -> float:
        return height - ((y - min_y) * scale + pad)

    solar_points = " ".join(f"{tx(point.x)},{ty(point.y)}" for point in pts)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}">',
        f'<polygon points="{solar_points}" fill="none" stroke="#333" stroke-width="2"/>',
    ]
    colors = ["#4A90D9", "#E67E22", "#27AE60", "#8E44AD", "#E74C3C"]
    for index, placement in enumerate(solution.placements):
        bbox = placement.bbox
        color = colors[index % len(colors)]
        x = tx(bbox.x)
        y = ty(bbox.y + bbox.height)
        box_width = bbox.width * scale
        box_height = bbox.height * scale
        cx = tx(bbox.x + bbox.width / 2.0)
        cy = ty(bbox.y + bbox.height / 2.0)
        lines.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{box_width:.1f}" height="{box_height:.1f}" '
            f'fill="{color}" fill-opacity="0.5" stroke="{color}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="8" text-anchor="middle" fill="#333">'
            f"{placement.typology_id}</text>"
        )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


async def _run_generation_job(
    app: FastAPI,
    job_id: str,
    project_id: str,
    version_id: str,
) -> None:
    repository = ProjectRepository(app.state.session_factory)
    job_manager: JobManager = app.state.job_manager
    output_root: Path = app.state.output_root

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
        program: Program = version.get_program_model()

        await job_manager.publish(job_id, "solver_started", status="running")
        await job_manager.publish(
            job_id,
            "solver_progress",
            data={"fraction_completed": None, "measurable": False},
        )
        solution = await asyncio.to_thread(
            solve,
            solar,
            program,
            app.state.settings.solver_timeout_seconds,
        )
        await repository.update_project_version(version_id, solution=solution)
        await job_manager.publish(
            job_id,
            "solver_finished",
            data={
                "status": solution.status,
                "num_units_placed": solution.metrics.num_units_placed,
            },
        )

        if solution.status not in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE):
            logger.warning("La generación del proyecto '%s' resultó inviable", project_id)
            await job_manager.fail(
                job_id,
                code="INFEASIBLE_SOLUTION",
                message=translate_error("INFEASIBLE_SOLUTION"),
            )
            return

        await job_manager.publish(job_id, "builder_started")
        building = await asyncio.to_thread(build_building_from_solution, solar, program, solution)

        version = await repository.get_project_version(version_id)
        assert version is not None
        project_output_dir = output_root / project_id / f"v{version.version_number}"
        project_output_dir.mkdir(parents=True, exist_ok=True)

        await job_manager.publish(
            job_id,
            "export_started",
            data={"formats": ["ifc", "dxf", "xlsx", "svg"]},
        )

        outputs = {
            "IFC": (project_output_dir / "model.ifc", "application/x-step"),
            "DXF": (project_output_dir / "model.dxf", "application/dxf"),
            "XLSX": (
                project_output_dir / "report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "SVG": (project_output_dir / "preview.svg", "image/svg+xml"),
        }

        await asyncio.to_thread(export_to_ifc, building, outputs["IFC"][0])
        await asyncio.to_thread(export_to_dxf, building, outputs["DXF"][0])
        await asyncio.to_thread(export_to_xlsx, building, program, outputs["XLSX"][0])
        await asyncio.to_thread(_draw_svg, solar, solution, outputs["SVG"][0])

        for output_type, (file_path, media_type) in outputs.items():
            await repository.create_generated_output(
                version_id,
                output_type=output_type,
                file_path=str(file_path),
                media_type=media_type,
                output_metadata={"size_bytes": file_path.stat().st_size},
            )

        await job_manager.finish(job_id, output_formats=[key.lower() for key in outputs])
    except Exception:  # noqa: BLE001
        logger.exception("Fallo inesperado durante la generación del proyecto '%s'", project_id)
        await job_manager.fail(
            job_id,
            code="GENERATION_FAILED",
            message=translate_error("GENERATION_FAILED"),
        )


@router.post(
    "/projects/{project_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStartResponse,
)
async def generate_project(
    project_id: str,
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

    logger.info("Iniciando job de generación para el proyecto '%s'", project_id)
    job = job_manager.create_job(project_id=project_id, version_id=version.id)
    task = asyncio.create_task(_run_generation_job(request.app, job.id, project_id, version.id))
    job_manager.set_task(job.id, task)
    return JobStartResponse(job_id=job.id, status=job.status, project_id=project_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> JobStatusResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise job_not_found(job_id)
    return JobStatusResponse(
        job_id=job.id,
        project_id=job.project_id,
        version_id=job.version_id,
        status=job.status,
        output_formats=job.output_formats,
        error=(
            JobErrorResponse(code=job.error_code, message=job.error_message or "")
            if job.error_code is not None
            else None
        ),
        events=[JobEventResponse.model_validate(event) for event in job.events],
    )


@router.websocket("/jobs/{job_id}/stream")
async def stream_job(
    websocket: WebSocket,
    job_id: str,
) -> None:
    job_manager: JobManager = websocket.app.state.job_manager
    job = job_manager.get_job(job_id)
    await websocket.accept()
    if job is None:
        await websocket.send_json(
            {"error": {"code": "JOB_NOT_FOUND", "message": translate_error("JOB_NOT_FOUND")}}
        )
        await websocket.close(code=4404)
        return

    backlog, queue = job_manager.subscribe(job_id)
    try:
        for event in backlog:
            await websocket.send_json(event)
        if job.status in {"finished", "failed"}:
            await websocket.close()
            return

        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["event"] in {"finished", "failed"}:
                await websocket.close()
                return
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado del job '%s'", job_id)
    finally:
        job_manager.unsubscribe(job_id, queue)