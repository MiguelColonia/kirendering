"""
Herramienta de optimización espacial para el agente copiloto.

Envuelve solver.engine.solve() exponiendo una interfaz tipada con Pydantic
y una definición de herramienta en formato Ollama para tool-calling.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import Solution, SolutionStatus
from cimiento.solver.engine import solve


class SolveResult(BaseModel):
    """Resultado de la herramienta solve_distribution."""

    status: SolutionStatus = Field(..., description="Estado de la resolución")
    num_units_placed: int = Field(..., description="Número de unidades colocadas")
    total_area_m2: float = Field(..., description="Superficie útil total asignada en m²")
    typology_fulfillment: dict[str, float] = Field(
        ...,
        description="Porcentaje de cumplimiento por tipología (0.0–1.0)",
    )
    solver_time_seconds: float = Field(..., description="Tiempo de cómputo en segundos")
    message: str | None = Field(default=None, description="Mensaje de diagnóstico si procede")
    solution: Solution = Field(..., description="Solución completa para herramientas posteriores")


def solve_distribution(
    solar: Solar,
    program: Program,
    timeout_seconds: int = 60,
) -> SolveResult:
    """
    Ejecuta el solver CP-SAT y devuelve la distribución óptima de viviendas.

    Parámetros
    ----------
    solar:
        Terreno con contorno poligonal y condiciones urbanísticas.
    program:
        Mix de tipologías con el número de unidades requeridas.
    timeout_seconds:
        Tiempo máximo de resolución (1–300 s, por defecto 60).
    """
    solution = solve(solar, program, timeout_seconds=timeout_seconds)
    return SolveResult(
        status=solution.status,
        num_units_placed=solution.metrics.num_units_placed,
        total_area_m2=solution.metrics.total_assigned_area,
        typology_fulfillment=solution.metrics.typology_fulfillment,
        solver_time_seconds=solution.solver_time_seconds,
        message=solution.message,
        solution=solution,
    )


# ---------------------------------------------------------------------------
# Definición en formato Ollama para tool-calling
# ---------------------------------------------------------------------------

SOLVE_DISTRIBUTION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "solve_distribution",
        "description": (
            "Ejecuta el optimizador espacial CP-SAT para distribuir las viviendas del programa "
            "sobre el solar del proyecto activo. "
            "Devuelve el estado (OPTIMAL / FEASIBLE / INFEASIBLE / TIMEOUT), "
            "el número de unidades colocadas, la superficie total asignada y el porcentaje "
            "de cumplimiento por tipología. "
            "Úsala cuando el arquitecto quiera calcular la distribución o saber cuántas "
            "viviendas caben."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timeout_seconds": {
                    "type": "integer",
                    "description": (
                        "Tiempo máximo de resolución en segundos. "
                        "Usa 30 para una respuesta rápida, 120 si el solar es complejo. "
                        "Por defecto 60."
                    ),
                    "default": 60,
                    "minimum": 1,
                    "maximum": 300,
                }
            },
            "required": [],
        },
    },
}
