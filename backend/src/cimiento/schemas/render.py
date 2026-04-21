"""
Schemas de entrada y salida de la capa de render (Fase 8).

RenderConfig es la única entrada pública al pipeline; RenderResult es la
salida. Todos los paths se resuelven a absolutos antes de pasarlos a Blender.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class RenderDevice(StrEnum):
    """Dispositivo de cómputo Cycles solicitado al invocar el pipeline."""

    HIP = "HIP"
    CPU = "CPU"
    AUTO = "AUTO"


class RenderConfig(BaseModel):
    """Parámetros de entrada para un trabajo de render de un modelo IFC."""

    ifc_path: Path = Field(..., description="Ruta absoluta al archivo IFC a renderizar")
    project_id: str = Field(
        ..., description="Identificador del proyecto; define la carpeta de salida"
    )
    output_dir: Path = Field(..., description="Carpeta raíz donde se guardarán los PNGs")
    north_angle_deg: float = Field(
        0.0,
        ge=0.0,
        lt=360.0,
        description="Ángulo norte del Solar en grados; orienta el sol en la escena",
    )
    render_width: int = Field(2048, gt=0, description="Anchura de render en píxeles (2K = 2048)")
    render_height: int = Field(
        1152, gt=0, description="Altura de render en píxeles (2K 16:9 = 1152)"
    )
    samples: int = Field(
        64,
        gt=0,
        description="Muestras Cycles por píxel; 64 es equilibrio calidad/tiempo en GPU",
    )
    device: RenderDevice = Field(
        RenderDevice.AUTO,
        description="AUTO prueba HIP (RX 6600) y cae a CPU si no está disponible",
    )
    blender_executable: Path = Field(
        Path("blender"),
        description="Ruta al binario de Blender; por defecto asume que está en PATH",
    )
    timeout_seconds: int = Field(
        600,
        gt=0,
        description="Timeout máximo por vista en segundos antes de abortar",
    )

    @field_validator("ifc_path")
    @classmethod
    def ifc_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"IFC no encontrado: {v}")
        return v.resolve()

    @field_validator("output_dir")
    @classmethod
    def resolve_output_dir(cls, v: Path) -> Path:
        return v.resolve()


class RenderView(BaseModel):
    """Resultado de una vista renderizada individualmente."""

    name: str = Field(..., description="Nombre de la vista (exterior_34, aerial, interior_0, …)")
    output_path: Path = Field(..., description="Ruta al PNG generado")
    duration_seconds: float = Field(..., description="Tiempo de render de esta vista en segundos")


class RenderResult(BaseModel):
    """Resultado completo de un trabajo de render: rutas a los PNGs y métricas de tiempo."""

    project_id: str
    output_dir: Path
    views: list[RenderView] = Field(default_factory=list)
    total_duration_seconds: float = Field(0.0)
    device_used: str = Field("", description="Dispositivo realmente utilizado por Cycles")
    blender_version: str = Field("", description="Versión de Blender usada")
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "RenderConfig",
    "RenderDevice",
    "RenderResult",
    "RenderView",
]
