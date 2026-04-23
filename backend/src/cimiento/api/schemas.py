"""
Schemas Pydantic de la capa API de Cimiento.

Estos schemas son exclusivos de la interfaz HTTP/WebSocket; no pertenecen
a los schemas de dominio (``cimiento.schemas``). Separan el contrato de API
del modelo interno para poder evolucionar ambos de forma independiente.

Grupos:
  - Requests de proyecto (create, update, patch program/solar)
  - Requests de render y difusión
  - Responses de job (start, status, eventos WebSocket)
  - Responses de galería (renders y difusión)
  - Responses de visión (plan interpreter)
  - Health check
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from cimiento.schemas import Program, Solar, Solution
from cimiento.schemas.diffusion import DiffusionMode


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


class ProjectPatchProgramRequest(BaseModel):
    """Payload para actualizar solo el programa de un proyecto."""

    program: Program


class ProjectPatchSolarRequest(BaseModel):
    """Payload para actualizar solo el solar de un proyecto."""

    solar: Solar


class RenderCreateRequest(BaseModel):
    """Payload para lanzar un render desde la API pública."""

    view: Literal["exterior", "interior"]
    prompt: str | None = None
    reference_image_name: str | None = None
    reference_image_base64: str | None = None
    reference_image_media_type: str | None = None


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


class RenderGalleryItemResponse(BaseModel):
    """Elemento serializado de la galería de renders de un proyecto."""

    id: str
    project_id: str
    version_id: str
    version_number: int
    view: Literal["exterior", "interior"]
    prompt: str | None = None
    image_url: str
    download_url: str
    media_type: str | None = None
    created_at: datetime
    has_reference_image: bool = False
    reference_image_name: str | None = None
    duration_seconds: float | None = None
    estimated_total_seconds: int | None = None
    device_used: str | None = None


class PixelBBoxResponse(BaseModel):
    """Caja delimitadora en píxeles para respuestas de visión."""

    x: int
    y: int
    width: int
    height: int


class DetectedSymbolResponse(BaseModel):
    """Símbolo arquitectónico detectado por el VLM."""

    symbol_type: str
    bbox_px: PixelBBoxResponse
    confidence: float


class DetectedLabelResponse(BaseModel):
    """Etiqueta de texto reconocida en el plano."""

    bbox_px: PixelBBoxResponse
    raw_text: str
    room_type: str | None


class RoomRegionResponse(BaseModel):
    """Región de estancia identificada por el VLM."""

    label_text: str | None
    room_type: str
    center_px: tuple[int, int]
    approx_bbox_px: PixelBBoxResponse


class PlanInterpretationResponse(BaseModel):
    """Resultado de la análisis visual de un plano. Siempre es un borrador que requiere revisión."""

    image_width_px: int
    image_height_px: int
    meters_per_pixel: float | None
    detected_symbols: list[DetectedSymbolResponse] = Field(default_factory=list)
    detected_labels: list[DetectedLabelResponse] = Field(default_factory=list)
    room_regions: list[RoomRegionResponse] = Field(default_factory=list)
    wall_segment_count: int
    has_draft_building: bool
    is_draft: bool
    review_required: bool
    warnings: list[str] = Field(default_factory=list)


class DiffusionCreateRequest(BaseModel):
    """Payload para lanzar un job de difusión."""

    mode: DiffusionMode
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = ""
    guidance_scale: float = Field(7.5, ge=1.0, le=20.0)
    image_guidance_scale: float = Field(1.5, ge=1.0, le=10.0)
    controlnet_conditioning_scale: float = Field(1.0, ge=0.0, le=2.0)
    seed: int | None = None


class DiffusionGalleryItemResponse(BaseModel):
    """Elemento de la galería de imágenes de difusión de un proyecto."""

    id: str
    project_id: str
    version_id: str
    version_number: int
    mode: DiffusionMode
    prompt: str | None = None
    image_url: str
    download_url: str
    media_type: str | None = None
    created_at: datetime
    duration_seconds: float | None = None
    device_used: str | None = None
    warnings: list[str] = Field(default_factory=list)


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
