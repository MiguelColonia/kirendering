"""Schemas Pydantic específicos de la capa API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from cimiento.schemas import Program, Solar, Solution


class ProjectCreateRequest(BaseModel):
    """Payload de creación de proyecto con snapshot inicial."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    solar: Solar
    program: Program


class ProjectUpdateRequest(BaseModel):
    """Payload de actualización lógica: crea una nueva versión del proyecto."""

    name: str | None = None
    description: str | None = None
    solar: Solar
    program: Program


class GeneratedOutputResponse(BaseModel):
    """Representación serializada de un archivo generado para el frontend."""

    id: str
    output_type: str
    file_path: str
    media_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ProjectVersionResponse(BaseModel):
    """Versión serializada de un proyecto con sus snapshots y outputs."""

    id: str
    version_number: int
    solar: Solar
    program: Program
    solution: Solution | None = None
    generated_outputs: list[GeneratedOutputResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectSummaryResponse(BaseModel):
    """Resumen ligero de proyecto para listados."""

    id: str
    name: str
    description: str | None = None
    latest_version_number: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectSummaryResponse):
    """Detalle completo de proyecto con su versión actual."""

    current_version: ProjectVersionResponse | None = None


class JobErrorResponse(BaseModel):
    """Error observable asociado a un job de generación."""

    code: str
    message: str


class JobEventResponse(BaseModel):
    """Evento emitido durante la ejecución de un job."""

    event: str
    job_id: str
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class JobStartResponse(BaseModel):
    """Respuesta inmediata al lanzar un job de generación."""

    job_id: str
    status: str
    project_id: str


class JobStatusResponse(BaseModel):
    """Estado observable y acumulado de un job de generación."""

    job_id: str
    project_id: str
    version_id: str
    status: str
    output_formats: list[str] = Field(default_factory=list)
    error: JobErrorResponse | None = None
    events: list[JobEventResponse] = Field(default_factory=list)


class ServiceHealthResponse(BaseModel):
    """Resultado de la comprobación de un servicio dependiente."""

    status: str
    detail: str | None = None
    code: str | None = None


class HealthResponse(BaseModel):
    """Respuesta agregada del endpoint de salud."""

    status: str
    app: str
    services: dict[str, ServiceHealthResponse]