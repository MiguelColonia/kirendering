"""
Herramienta de validación de viabilidad para el agente copiloto.

Realiza comprobaciones geométricas y de programa rápidas (sin solver) que permiten
dar retroalimentación inmediata al arquitecto antes de lanzar el optimizador CP-SAT.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from shapely.geometry import Polygon as ShapelyPolygon

from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar

# Rendimiento de ocupación típico en vivienda colectiva (área útil / área bruta de planta)
_TYPICAL_FLOOR_EFFICIENCY = 0.70

# Ratio mínimo solar/tipología para que una unidad tenga posibilidades reales de caber
_MIN_SOLAR_TO_UNIT_RATIO = 1.5


class IssueLevel(StrEnum):
    """Nivel de gravedad de un problema detectado."""

    ERROR = "ERROR"
    """Impide la resolución: el solver fallará con seguridad."""

    WARNING = "WARNING"
    """El solver puede encontrar solución pero con restricciones ajustadas."""

    INFO = "INFO"
    """Observación relevante sin impacto en la resolución."""


class FeasibilityIssue(BaseModel):
    """Problema individual detectado durante la validación de viabilidad."""

    level: IssueLevel
    code: str = Field(..., description="Código corto identificador del problema")
    message: str = Field(..., description="Descripción legible del problema")


class FeasibilityReport(BaseModel):
    """Informe de viabilidad del programa sobre el solar."""

    is_feasible: bool = Field(
        ...,
        description="True si no se detectaron errores bloqueantes",
    )
    solar_area_m2: float = Field(..., description="Superficie del solar en m²")
    required_area_m2: float = Field(
        ...,
        description="Superficie útil total requerida por el programa en m²",
    )
    estimated_buildable_area_m2: float = Field(
        ...,
        description=(
            "Estimación de superficie edificable considerando el número de plantas "
            "y un rendimiento típico de ocupación"
        ),
    )
    issues: list[FeasibilityIssue] = Field(
        default_factory=list,
        description="Lista de problemas detectados, ordenados por gravedad",
    )


def validate_program_feasibility(solar: Solar, program: Program) -> FeasibilityReport:
    """
    Comprueba la viabilidad geométrica del programa sobre el solar sin ejecutar el solver.

    Detecta errores bloqueantes (tipologías más grandes que el solar, programa
    incompatible con la altura máxima) y avisos (programa muy ajustado, número
    de plantas elevado respecto a la altura permitida).

    Parámetros
    ----------
    solar:
        Terreno con contorno poligonal y condiciones urbanísticas.
    program:
        Mix de tipologías con el número de unidades requeridas.
    """
    issues: list[FeasibilityIssue] = []

    # --- Área del solar ---
    solar_poly = ShapelyPolygon([(p.x, p.y) for p in solar.contour.points])
    solar_area = solar_poly.area

    # --- Superficie útil total requerida ---
    typology_map = {t.id: t for t in program.typologies}
    required_area = sum(
        typology_map[entry.typology_id].min_useful_area * entry.count
        for entry in program.mix
    )

    # --- Superficie edificable estimada ---
    estimated_buildable = solar_area * program.num_floors * _TYPICAL_FLOOR_EFFICIENCY

    # --- Comprobación 1: altura máxima vs número de plantas ---
    max_floors_by_height = int(solar.max_buildable_height_m / program.floor_height_m)
    if program.num_floors > max_floors_by_height:
        issues.append(FeasibilityIssue(
            level=IssueLevel.ERROR,
            code="HEIGHT_EXCEEDED",
            message=(
                f"El programa solicita {program.num_floors} plantas pero la altura máxima "
                f"({solar.max_buildable_height_m} m) solo permite {max_floors_by_height} plantas "
                f"con alturas de {program.floor_height_m} m."
            ),
        ))

    # --- Comprobación 2: programa requiere más superficie de la edificable ---
    if required_area > estimated_buildable:
        issues.append(FeasibilityIssue(
            level=IssueLevel.ERROR,
            code="AREA_INFEASIBLE",
            message=(
                f"El programa requiere {required_area:.0f} m² útiles pero la superficie "
                f"edificable estimada ({estimated_buildable:.0f} m²) es insuficiente. "
                f"Considera reducir el número de unidades o aumentar las plantas."
            ),
        ))
    elif required_area > estimated_buildable * 0.90:
        issues.append(FeasibilityIssue(
            level=IssueLevel.WARNING,
            code="AREA_TIGHT",
            message=(
                f"El programa ocupa el {required_area / estimated_buildable * 100:.0f}% "
                "de la superficie edificable estimada. El solver puede tardar más o "
                "encontrar solución subóptima."
            ),
        ))

    # --- Comprobación 3: tipologías mayores que el solar ---
    min_x, min_y, max_x, max_y = solar.contour.bounding_box
    solar_bbox_w = max_x - min_x
    solar_bbox_h = max_y - min_y

    for typology in program.typologies:
        # Dimensión mínima esperada: raíz cuadrada del área mínima asumiendo proporción 7:h
        unit_w = 7.0
        unit_h = typology.min_useful_area / unit_w
        if unit_w > solar_bbox_w or unit_h > solar_bbox_h:
            issues.append(FeasibilityIssue(
                level=IssueLevel.ERROR,
                code="UNIT_TOO_LARGE",
                message=(
                    f"La tipología '{typology.id}' ({typology.min_useful_area} m²) "
                    f"requiere una forma aproximada de {unit_w:.1f} m × {unit_h:.1f} m "
                    f"que no cabe en el solar "
                    f"({solar_bbox_w:.1f} m × {solar_bbox_h:.1f} m)."
                ),
            ))

    # --- Comprobación 4: programa vacío ---
    if not program.mix:
        issues.append(FeasibilityIssue(
            level=IssueLevel.INFO,
            code="EMPTY_PROGRAM",
            message=(
                "El programa no contiene unidades en el mix. "
                "El solver devolverá una solución vacía."
            ),
        ))

    # --- Comprobación 5: solar con área muy pequeña ---
    if solar_area < 200:
        issues.append(FeasibilityIssue(
            level=IssueLevel.WARNING,
            code="SMALL_SOLAR",
            message=(
                f"El solar tiene {solar_area:.0f} m², lo que puede limitar "
                "la capacidad de núcleos de comunicación y circulaciones."
            ),
        ))

    has_errors = any(i.level == IssueLevel.ERROR for i in issues)
    # Ordenar: errores primero, luego warnings, luego info
    level_order = {IssueLevel.ERROR: 0, IssueLevel.WARNING: 1, IssueLevel.INFO: 2}
    issues.sort(key=lambda i: level_order[i.level])

    return FeasibilityReport(
        is_feasible=not has_errors,
        solar_area_m2=round(solar_area, 2),
        required_area_m2=round(required_area, 2),
        estimated_buildable_area_m2=round(estimated_buildable, 2),
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Definición en formato Ollama para tool-calling
# ---------------------------------------------------------------------------

VALIDATE_FEASIBILITY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "validate_program_feasibility",
        "description": (
            "Comprueba rápidamente si el programa de viviendas es viable sobre el solar "
            "sin ejecutar el optimizador completo. "
            "Detecta errores bloqueantes (tipologías demasiado grandes, superficie insuficiente, "
            "altura normativa superada) y avisos (programa muy ajustado, solar pequeño). "
            "Úsala antes de solve_distribution o cuando el arquitecto pregunte si un programa "
            "es posible en el solar."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}
