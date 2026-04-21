"""
Tool de sugerencia de ajustes tipológicos para el agente copiloto.

Dado un programa y una solución infactible o subóptima, propone modificaciones
concretas y deterministas (sin LLM) para aumentar la probabilidad de resolución.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from cimiento.schemas.program import Program, TypologyMix
from cimiento.schemas.solution import Solution, SolutionStatus


class AdjustmentSuggestion(BaseModel):
    """Sugerencia de ajuste al programa para mejorar la resolución."""

    reason: str = Field(..., description="Motivo del ajuste en términos arquitectónicos")
    adjusted_program: Program = Field(
        ...,
        description=(
            "Versión modificada del programa que puede ser probada directamente "
            "en solve_layout. Solo se modifican los campos necesarios."
        ),
    )
    impact_summary: str = Field(
        ...,
        description=(
            "Descripción concisa del impacto del ajuste: "
            "qué se reduce/aumenta y en qué medida"
        ),
    )


class AdjustmentResult(BaseModel):
    """Resultado del análisis de ajustes tipológicos."""

    original_status: SolutionStatus
    suggestions: list[AdjustmentSuggestion] = Field(
        default_factory=list,
        description="Lista de sugerencias ordenadas de menor a mayor impacto en el programa",
    )
    explanation: str = Field(
        ...,
        description="Diagnóstico breve de por qué el programa original no es óptimo",
    )


# ---------------------------------------------------------------------------
# Factores de reducción aplicados en cada sugerencia
# ---------------------------------------------------------------------------

_REDUCTION_MILD = 0.80      # reducción del 20 %
_REDUCTION_MODERATE = 0.65  # reducción del 35 %
_REDUCTION_AGGRESSIVE = 0.50  # reducción del 50 %


def _reduce_mix(program: Program, factor: float) -> Program:
    """Devuelve una copia del programa con el mix reducido por el factor dado."""
    new_mix = [
        TypologyMix(
            typology_id=entry.typology_id,
            count=max(1, math.ceil(entry.count * factor)),
        )
        for entry in program.mix
    ]
    return program.model_copy(update={"mix": new_mix})


def _add_floor(program: Program) -> Program:
    """Devuelve una copia del programa con una planta adicional."""
    return program.model_copy(update={"num_floors": program.num_floors + 1})


def suggest_typology_adjustments(
    program: Program,
    solution: Solution,
    max_suggestions: int = 3,
) -> AdjustmentResult:
    """
    Propone ajustes deterministas al programa para mejorar la resolución.

    Estrategia
    ----------
    - INFEASIBLE: el programa es imposible para el solar dado.
      → Sugerencias: reducción progresiva del mix (20 %, 35 %, 50 %).
    - TIMEOUT: el solver agotó el tiempo sin solución.
      → Sugerencias: reducción leve del mix + añadir una planta.
    - FEASIBLE con cumplimiento bajo en alguna tipología:
      → Sugerencias: reducción proporcional a la tipología con peor cumplimiento.
    - OPTIMAL: no se proponen ajustes.

    Parámetros
    ----------
    program:
        Programa original que produjo la solución.
    solution:
        Resultado del solver a analizar.
    max_suggestions:
        Número máximo de sugerencias a generar (1–5).
    """
    max_suggestions = max(1, min(max_suggestions, 5))
    suggestions: list[AdjustmentSuggestion] = []

    total_requested = sum(e.count for e in program.mix)

    if solution.status == SolutionStatus.OPTIMAL:
        return AdjustmentResult(
            original_status=solution.status,
            suggestions=[],
            explanation=(
                "La solución es óptima. No se proponen ajustes: "
                "el programa se cumple al 100 % dentro del solar."
            ),
        )

    if solution.status == SolutionStatus.INFEASIBLE:
        explanation = (
            f"El programa de {total_requested} unidades no cabe en el solar con la "
            "configuración actual. Las unidades son demasiado grandes para el polígono "
            "disponible o el número de plantas es insuficiente."
        )
        reductions = [_REDUCTION_MILD, _REDUCTION_MODERATE, _REDUCTION_AGGRESSIVE]
        for factor in reductions[:max_suggestions]:
            reduced = _reduce_mix(program, factor)
            new_total = sum(e.count for e in reduced.mix)
            suggestions.append(AdjustmentSuggestion(
                reason=(
                    f"Reducir el mix al {round(factor * 100):.0f} % del original "
                    f"({new_total} unidades en lugar de {total_requested})"
                ),
                adjusted_program=reduced,
                impact_summary=(
                    f"Se pasa de {total_requested} a {new_total} unidades "
                    f"(reducción del {round((1 - factor) * 100):.0f} %)."
                ),
            ))
            if len(suggestions) >= max_suggestions:
                break
        # Añadir planta como alternativa si cabe en max_suggestions
        if len(suggestions) < max_suggestions:
            with_floor = _add_floor(program)
            suggestions.append(AdjustmentSuggestion(
                reason=(
                    f"Añadir una planta al programa "
                    f"({program.num_floors} → {with_floor.num_floors} plantas) "
                    "manteniendo el mismo mix"
                ),
                adjusted_program=with_floor,
                impact_summary=(
                    f"El volumen edificable aumenta en ~{program.num_floors + 1} "
                    f"veces la superficie de planta."
                ),
            ))

    elif solution.status in (SolutionStatus.TIMEOUT, SolutionStatus.FEASIBLE):
        fulfillment = solution.metrics.typology_fulfillment
        worst_tid = min(fulfillment, key=lambda t: fulfillment[t]) if fulfillment else None
        worst_rate = fulfillment.get(worst_tid, 1.0) if worst_tid else 1.0

        if worst_rate < 0.99:
            explanation = (
                f"El solver colocó {solution.metrics.num_units_placed} de "
                f"{total_requested} unidades solicitadas "
                + ("TIMEOUT: sin solución óptima"
                   if solution.status == SolutionStatus.TIMEOUT
                   else "solución parcial")
                + ")."
            )
            # Sugerencia 1: reducción proporcional al peor cumplimiento
            factor = max(_REDUCTION_MILD, worst_rate)
            reduced = _reduce_mix(program, factor)
            new_total = sum(e.count for e in reduced.mix)
            suggestions.append(AdjustmentSuggestion(
                reason=(
                    f"Ajustar el mix al cumplimiento observado ({round(worst_rate * 100):.0f} %) "
                    f"de la tipología con peor resultado"
                    + (f" ('{worst_tid}')" if worst_tid else "")
                ),
                adjusted_program=reduced,
                impact_summary=(
                    f"De {total_requested} a {new_total} unidades "
                    f"(factor {round(factor, 2):.2f})."
                ),
            ))
            # Sugerencia 2: añadir planta
            if len(suggestions) < max_suggestions:
                with_floor = _add_floor(program)
                suggestions.append(AdjustmentSuggestion(
                    reason=(
                        f"Añadir una planta ({program.num_floors} → {with_floor.num_floors}) "
                        "para dar más capacidad al solver"
                    ),
                    adjusted_program=with_floor,
                    impact_summary=(
                        "La distribución dispone de más superficie; "
                        "puede mejorar el cumplimiento sin reducir el mix."
                    ),
                ))
        else:
            explanation = (
                "La solución alcanza un cumplimiento alto. "
                "Si se desea optimizar más, prueba a aumentar el timeout del solver."
            )
    else:
        explanation = (
            f"Estado inesperado del solver: {solution.status}. "
            "Revisa el mensaje de error del solver antes de intentar ajustes."
        )

    return AdjustmentResult(
        original_status=solution.status,
        suggestions=suggestions[:max_suggestions],
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Definición Ollama para tool-calling
# ---------------------------------------------------------------------------

SUGGEST_ADJUSTMENTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "suggest_typology_adjustments",
        "description": (
            "Dado un programa y una solución infactible o subóptima, propone ajustes "
            "concretos al mix de viviendas (reducir unidades, añadir planta) que aumentan "
            "la probabilidad de resolución. Los ajustes son deterministas, sin LLM. "
            "Úsala cuando solve_layout devuelva INFEASIBLE, TIMEOUT o cumplimiento bajo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_suggestions": {
                    "type": "integer",
                    "description": "Número máximo de sugerencias a generar (1–5). Por defecto 3.",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                }
            },
            "required": [],
        },
    },
}
