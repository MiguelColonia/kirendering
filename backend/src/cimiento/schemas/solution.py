"""
Resultado devuelto por el solver tras la optimización espacial.

Una Solution contiene el estado de la resolución, la lista de colocaciones de
viviendas con sus posiciones en planta, métricas agregadas de calidad y metadatos
del proceso de optimización (tiempo de cómputo, mensajes de diagnóstico).
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from cimiento.schemas.architectural import CommunicationCore, ParkingStorey
from cimiento.schemas.geometry_primitives import Rectangle


class SolutionStatus(StrEnum):
    """Estado de la resolución devuelto por el solver."""

    OPTIMAL = "OPTIMAL"
    """Solución óptima probada: no existe ninguna solución mejor."""

    FEASIBLE = "FEASIBLE"
    """Solución factible encontrada pero no probada óptima (límite de tiempo alcanzado)."""

    INFEASIBLE = "INFEASIBLE"
    """El problema no tiene solución: el solar o las restricciones son incompatibles."""

    TIMEOUT = "TIMEOUT"
    """El solver agotó el tiempo permitido sin encontrar ninguna solución factible."""

    ERROR = "ERROR"
    """Error interno del solver o del modelo; consultar el campo message."""


class UnitPlacement(BaseModel):
    """
    Colocación concreta de una unidad residencial en la solución.

    Asocia una tipología con su planta y su rectángulo de ocupación en planta,
    expresado en el mismo sistema de referencia que el Solar de entrada.
    """

    typology_id: str = Field(
        ...,
        description="Identificador de la tipología asignada a esta unidad",
    )
    floor: int = Field(
        ...,
        ge=0,
        description="Número de planta (0 = planta baja, 1 = primera planta, etc.)",
    )
    bbox: Rectangle = Field(
        ...,
        description=(
            "Rectángulo delimitador que ocupa la unidad en planta, "
            "en metros y en el sistema de referencia del solar"
        ),
    )


class SolutionMetrics(BaseModel):
    """
    Indicadores agregados de calidad de la solución.

    Permiten evaluar de un vistazo si el solver satisfizo el programa
    y cuánto espacio útil fue asignado en total.
    """

    total_assigned_area: float = Field(
        ...,
        ge=0.0,
        description="Superficie útil total asignada en m², suma de las áreas de todos los bbox",
    )
    num_units_placed: int = Field(
        ...,
        ge=0,
        description="Número total de unidades residenciales colocadas en la solución",
    )
    typology_fulfillment: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Porcentaje de cumplimiento por tipología (0.0–1.0); "
            "clave: typology_id, valor: unidades_colocadas / unidades_requeridas"
        ),
    )


class Solution(BaseModel):
    """
    Solución completa devuelta por el solver.

    Contiene el estado de la resolución, las colocaciones individuales,
    las métricas de calidad y metadatos del proceso de optimización.
    """

    status: SolutionStatus = Field(
        ...,
        description="Estado de la resolución: OPTIMAL, FEASIBLE, INFEASIBLE, TIMEOUT o ERROR",
    )
    placements: list[UnitPlacement] = Field(
        default_factory=list,
        description="Lista de unidades colocadas con su tipología, planta y posición",
    )
    communication_cores: list[CommunicationCore] = Field(
        default_factory=list,
        description="Núcleos de comunicación vertical que estructuran la solución",
    )
    metrics: SolutionMetrics = Field(
        ...,
        description="Indicadores agregados de calidad de la solución",
    )
    solver_time_seconds: float = Field(
        ...,
        ge=0.0,
        description="Tiempo de CPU consumido por el solver en segundos",
    )
    message: str | None = Field(
        default=None,
        description=(
            "Mensaje descriptivo, presente cuando status es INFEASIBLE o ERROR; "
            "explica la causa del fallo o del resultado subóptimo"
        ),
    )


class ParkingSolutionMetrics(BaseModel):
    """Indicadores agregados del layout de aparcamiento."""

    total_spaces: int = Field(..., ge=0, description="Número total de plazas generadas")
    standard_spaces: int = Field(..., ge=0, description="Número de plazas estándar")
    accessible_spaces: int = Field(..., ge=0, description="Número de plazas accesibles")
    motorcycle_spaces: int = Field(..., ge=0, description="Número de plazas de motocicleta")
    required_spaces: int = Field(..., ge=0, description="Mínimo normativo de plazas exigidas")


class ParkingSolution(BaseModel):
    """Resultado de la subrutina de solver específica para aparcamiento."""

    status: SolutionStatus = Field(..., description="Estado de resolución del aparcamiento")
    storey: ParkingStorey | None = Field(
        default=None,
        description="Planta de aparcamiento generada; None si no existe solución",
    )
    metrics: ParkingSolutionMetrics = Field(
        ...,
        description="Métricas agregadas de la solución de aparcamiento",
    )
    solver_time_seconds: float = Field(
        ...,
        ge=0.0,
        description="Tiempo de cálculo del solver de parking en segundos",
    )
    message: str | None = Field(
        default=None,
        description="Mensaje descriptivo asociado al resultado del solver de parking",
    )
