"""Endpoints para descarga de outputs generados."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from cimiento.api.dependencies import get_repository
from cimiento.api.errors import api_error, output_not_found, project_not_found
from cimiento.persistence.repository import ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["downloads"])

_FORMAT_MAP = {
    "ifc": "IFC",
    "dxf": "DXF",
    "xlsx": "XLSX",
    "svg": "SVG",
}


@router.get("/{project_id}/outputs/{output_format}")
async def download_output(
    project_id: str,
    output_format: str,
    repository: ProjectRepository = Depends(get_repository),
) -> FileResponse:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    normalized = _FORMAT_MAP.get(output_format.lower())
    if normalized is None:
        raise api_error(400, "UNSUPPORTED_OUTPUT_FORMAT", output_format=output_format)

    version = await repository.get_latest_project_version(project_id)
    if version is None:
        raise api_error(409, "PROJECT_HAS_NO_VERSION", project_id=project_id)

    output = await repository.get_latest_generated_output(version.id, normalized)
    if output is None:
        raise output_not_found(project_id, output_format)

    file_path = Path(output.file_path)
    if not file_path.exists():
        logger.warning("El archivo de salida '%s' no existe en disco", output.file_path)
        raise output_not_found(project_id, output_format)

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=output.media_type or "application/octet-stream",
    )
