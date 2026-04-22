"""
Tool de cálculo de métricas urbanísticas para el agente copiloto.

Calcula indicadores de edificabilidad, ocupación y densidad a partir de
un Building y el Solar correspondiente. Sin LLM: operaciones numéricas puras.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from shapely.geometry import Polygon as ShapelyPolygon

from cimiento.schemas.architectural import Building, Space
from cimiento.schemas.solar import Solar


class UrbanMetrics(BaseModel):
    """Indicadores urbanísticos calculados sobre el edificio."""

    solar_area_m2: float = Field(..., ge=0.0, description="Superficie del solar en m²")

    total_gfa_m2: float = Field(
        ...,
        ge=0.0,
        description=(
            "Superficie bruta construida total (GFA): suma de áreas de todos los espacios "
            "en todas las plantas, en m²"
        ),
    )
    floor_area_ratio: float = Field(
        ...,
        ge=0.0,
        description=(
            "Índice de edificabilidad (FAR): GFA total / superficie del solar. "
            "Adimensional; p. ej. 1,5 significa 1,5 m² construidos por m² de solar."
        ),
    )
    site_coverage_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Ocupación del solar: área de la huella del edificio en planta baja / "
            "superficie del solar. Valor entre 0 y 1."
        ),
    )
    density_units_per_ha: float = Field(
        ...,
        ge=0.0,
        description="Densidad residencial: número de viviendas por hectárea de solar.",
    )
    num_units: int = Field(..., ge=0, description="Número total de unidades residenciales")
    num_floors: int = Field(..., ge=0, description="Número de plantas sobre rasante")
    avg_unit_area_m2: float = Field(
        ...,
        ge=0.0,
        description="Superficie media por unidad residencial en m²; 0 si no hay unidades",
    )


def _ground_floor_footprint_m2(building: Building) -> float:
    """Calcula el área de la huella del edificio en la planta baja (nivel 0)."""
    ground = next((s for s in building.storeys if s.level == 0), None)
    if ground is None:
        return 0.0
    return sum(_space_area(sp) for sp in ground.spaces)


def _space_area(space: Space) -> float:
    """Área del espacio a partir de su contorno Polygon2D."""
    pts = [(p.x, p.y) for p in space.contour.points]
    if len(pts) < 3:
        return 0.0
    return ShapelyPolygon(pts).area


def calculate_metrics(building: Building, solar: Solar) -> UrbanMetrics:
    """
    Calcula indicadores urbanísticos sobre el edificio proyectado.

    Métricas calculadas
    -------------------
    - FAR (índice de edificabilidad): GFA total / área solar
    - Ocupación (site coverage): huella PB / área solar
    - Densidad: viviendas / hectárea de solar
    - Nº de viviendas, plantas, área media por unidad

    Parámetros
    ----------
    building:
        Edificio con sus plantas y espacios generados por el builder.
    solar:
        Solar del proyecto; necesario para calcular FAR y ocupación.
    """
    solar_poly = ShapelyPolygon([(p.x, p.y) for p in solar.contour.points])
    solar_area = solar_poly.area

    # Superficie bruta construida: suma de áreas de todos los espacios en todas las plantas
    total_gfa = sum(_space_area(sp) for storey in building.storeys for sp in storey.spaces)

    footprint = _ground_floor_footprint_m2(building)

    num_units = sum(len(s.spaces) for s in building.storeys)
    above_grade_floors = sum(1 for s in building.storeys if s.level >= 0)

    far = total_gfa / solar_area if solar_area > 0 else 0.0
    coverage = footprint / solar_area if solar_area > 0 else 0.0
    density = num_units / (solar_area / 10_000) if solar_area > 0 else 0.0
    avg_area = total_gfa / num_units if num_units > 0 else 0.0

    return UrbanMetrics(
        solar_area_m2=round(solar_area, 2),
        total_gfa_m2=round(total_gfa, 2),
        floor_area_ratio=round(far, 3),
        site_coverage_ratio=round(min(coverage, 1.0), 3),
        density_units_per_ha=round(density, 1),
        num_units=num_units,
        num_floors=above_grade_floors,
        avg_unit_area_m2=round(avg_area, 2),
    )


# ---------------------------------------------------------------------------
# Definición Ollama para tool-calling
# ---------------------------------------------------------------------------

CALCULATE_METRICS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "calculate_metrics",
        "description": (
            "Calcula indicadores urbanísticos del proyecto: índice de edificabilidad (FAR), "
            "ocupación del solar, densidad de viviendas por hectárea, número de unidades "
            "y superficie media por vivienda. "
            "Requiere que el modelo BIM haya sido construido (build_and_export_ifc). "
            "Úsala cuando el arquitecto pregunte por indicadores, ratios o métricas del proyecto."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}
