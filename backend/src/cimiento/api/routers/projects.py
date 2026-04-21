"""Endpoints REST para gestión de proyectos persistidos."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status

from cimiento.api.dependencies import get_repository
from cimiento.api.errors import project_not_found
from cimiento.api.schemas import (
    GeneratedOutputResponse,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
    ProjectVersionResponse,
)
from cimiento.persistence.models import GeneratedOutput, Project, ProjectVersion
from cimiento.persistence.repository import ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_status(project: Project) -> str:
    latest_version = max(project.versions, key=lambda version: version.version_number, default=None)
    if latest_version is None or latest_version.solution_data is None:
        return "draft"

    return str(latest_version.solution_data.get("status", "draft")).lower()


def _serialize_output(output: GeneratedOutput) -> GeneratedOutputResponse:
    return GeneratedOutputResponse(
        id=output.id,
        output_type=output.output_type,
        file_path=output.file_path,
        media_type=output.media_type,
        metadata=output.output_metadata,
        created_at=output.created_at,
    )


def _serialize_version(version: ProjectVersion | None) -> ProjectVersionResponse | None:
    if version is None:
        return None
    return ProjectVersionResponse(
        id=version.id,
        version_number=version.version_number,
        solar=version.get_solar_model(),
        program=version.get_program_model(),
        solution=version.get_solution_model(),
        generated_outputs=[_serialize_output(output) for output in version.generated_outputs],
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _serialize_project_summary(project: Project) -> ProjectSummaryResponse:
    latest_version = max((version.version_number for version in project.versions), default=None)
    return ProjectSummaryResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        latest_version_number=latest_version,
        status=_project_status(project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _serialize_project_detail(
    project: Project,
    latest_version: ProjectVersion | None,
) -> ProjectDetailResponse:
    summary = _serialize_project_summary(project)
    return ProjectDetailResponse(
        **summary.model_dump(), current_version=_serialize_version(latest_version)
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectDetailResponse)
async def create_project(
    payload: ProjectCreateRequest,
    repository: ProjectRepository = Depends(get_repository),
) -> ProjectDetailResponse:
    logger.info("Creando proyecto persistido '%s'", payload.name)
    project = await repository.create_project(name=payload.name, description=payload.description)
    program = payload.program.model_copy(update={"project_id": project.id})
    version = await repository.create_project_version(
        project.id,
        solar=payload.solar,
        program=program,
    )
    project = await repository.get_project(project.id)
    assert project is not None
    version = await repository.get_project_version(version.id)
    return _serialize_project_detail(project, version)


@router.get("", response_model=list[ProjectSummaryResponse])
async def list_projects(
    repository: ProjectRepository = Depends(get_repository),
) -> list[ProjectSummaryResponse]:
    projects = await repository.list_projects()
    return [_serialize_project_summary(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    repository: ProjectRepository = Depends(get_repository),
) -> ProjectDetailResponse:
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)
    latest_version = await repository.get_latest_project_version(project_id)
    return _serialize_project_detail(project, latest_version)


@router.put("/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    repository: ProjectRepository = Depends(get_repository),
) -> ProjectDetailResponse:
    logger.info("Actualizando proyecto '%s' con nueva versión lógica", project_id)
    project = await repository.update_project(
        project_id,
        name=payload.name,
        description=payload.description,
    )
    if project is None:
        raise project_not_found(project_id)
    program = payload.program.model_copy(update={"project_id": project_id})
    version = await repository.create_project_version(
        project_id,
        solar=payload.solar,
        program=program,
    )
    project = await repository.get_project(project_id)
    assert project is not None
    version = await repository.get_project_version(version.id)
    return _serialize_project_detail(project, version)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    repository: ProjectRepository = Depends(get_repository),
) -> Response:
    logger.info("Eliminando proyecto '%s'", project_id)
    deleted = await repository.delete_project(project_id)
    if not deleted:
        raise project_not_found(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
