"""
Tool de optimización de layout para el agente copiloto.

Contrato completo Pydantic: el LLM devuelve JSON validado por SolveLayoutInput,
el solver CP-SAT se ejecuta y devuelve SolveLayoutOutput con la Solution embebida
para uso posterior por otras tools.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import Solution, SolutionStatus
from cimiento.solver.engine import solve


class SolveLayoutInput(BaseModel):
    """Entrada validada del tool solve_layout."""

    solar: Solar
    program: Program
    timeout_seconds: int = Field(default=60, ge=1, le=300)


class SolveLayoutOutput(BaseModel):
    """Resultado del tool solve_layout."""

    status: SolutionStatus
    num_units_placed: int = Field(..., ge=0)
    total_area_m2: float = Field(..., ge=0.0)
    typology_fulfillment: dict[str, float] = Field(
        ...,
        description="Fracción de cumplimiento por tipología (0.0 – 1.0)",
    )
    solver_time_seconds: float = Field(..., ge=0.0)
    message: str | None = None
    solution: Solution = Field(..., description="Solución completa para tools posteriores")


def solve_layout(input: SolveLayoutInput) -> SolveLayoutOutput:
    """
    Ejecuta el solver CP-SAT y devuelve la distribución óptima de viviendas.

    Acepta un SolveLayoutInput validado por Pydantic.
    Invoca solver.engine.solve() y empaqueta el resultado como SolveLayoutOutput.
    """
    solution = solve(
        solar=input.solar,
        program=input.program,
        timeout_seconds=input.timeout_seconds,
    )
    return SolveLayoutOutput(
        status=solution.status,
        num_units_placed=solution.metrics.num_units_placed,
        total_area_m2=solution.metrics.total_assigned_area,
        typology_fulfillment=solution.metrics.typology_fulfillment,
        solver_time_seconds=solution.solver_time_seconds,
        message=solution.message,
        solution=solution,
    )


# ---------------------------------------------------------------------------
# Definición Ollama para tool-calling
# ---------------------------------------------------------------------------

SOLVE_LAYOUT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "solve_layout",
        "description": (
            "Ejecuta el optimizador espacial CP-SAT para distribuir las viviendas del programa "
            "sobre el solar. Devuelve el estado de resolución (OPTIMAL / FEASIBLE / INFEASIBLE / "
            "TIMEOUT), el número de unidades colocadas, la superficie total y el porcentaje de "
            "cumplimiento por tipología. Úsala cuando el arquitecto quiera calcular "
            "la distribución o saber cuántas viviendas caben."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timeout_seconds": {
                    "type": "integer",
                    "description": (
                        "Tiempo máximo de resolución en segundos. "
                        "Usa 30 para respuesta rápida, 120 si el solar es complejo. "
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
