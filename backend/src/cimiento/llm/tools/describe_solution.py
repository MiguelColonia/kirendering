"""
Tool de descripción textual de una Solution en alemán para el agente copiloto.

Usa el modelo de chat (qwen2.5:7b) con instrucción estricta de basarse solo
en los datos proporcionados y no inventar información no presente en la solución.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cimiento.llm.client import OllamaClient
from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import Solution, SolutionStatus

_SYSTEM_PROMPT = """\
Du bist ein sachlicher Assistent für einen Architekten. \
Deine Aufgabe ist es, das Ergebnis einer Raumoptimierung klar und präzise \
auf Deutsch zu beschreiben.

REGELN:
1. Beschreibe ausschließlich die Daten, die dir übergeben werden.
2. Erfinde keine Werte, Flächen oder Einheiten, die nicht in den Daten enthalten sind.
3. Verwende Fachbegriffe der Architektur und Stadtplanung auf Deutsch.
4. Schreibe in vollständigen Sätzen, maximal 6 Sätze.
5. Fange mit dem Status der Lösung an (OPTIMAL, FEASIBLE, INFEASIBLE, TIMEOUT).
6. Nenne die Anzahl der platzierten Einheiten und den Erfüllungsgrad pro Typologie.
7. Erwähne die Grundstücksfläche und die belegte Nutzfläche.
8. Falls die Lösung INFEASIBLE oder TIMEOUT ist, erkläre kurz die Ursache aus den Daten.
"""

_STATUS_LABELS: dict[SolutionStatus, str] = {
    SolutionStatus.OPTIMAL: "OPTIMAL (beste mögliche Lösung)",
    SolutionStatus.FEASIBLE: "FEASIBLE (umsetzbare Lösung, nicht bewiesen optimal)",
    SolutionStatus.INFEASIBLE: "INFEASIBLE (keine Lösung möglich)",
    SolutionStatus.TIMEOUT: "TIMEOUT (Zeitlimit erreicht, keine Lösung gefunden)",
    SolutionStatus.ERROR: "FEHLER (interner Solver-Fehler)",
}


def _build_data_summary(solution: Solution, program: Program, solar: Solar) -> str:
    """Construye un resumen estructurado de los datos para el prompt de usuario."""
    total_requested = sum(e.count for e in program.mix)
    typology_names = {t.id: t.name for t in program.typologies}

    fulfillment_items: list[str] = []
    for entry in program.mix:
        tid = entry.typology_id
        rate = solution.metrics.typology_fulfillment.get(tid, 0.0)
        requested = total_requests_for(tid, program)
        placed = round(rate * requested)
        name = typology_names.get(tid, tid)
        fulfillment_items.append(
            f"  - {name}: {rate * 100:.0f} % ({placed} von {requested} Einheiten)"
        )
    fulfillment_lines = "\n".join(fulfillment_items)

    min_x, min_y, max_x, max_y = solar.contour.bounding_box
    solar_w = max_x - min_x
    solar_h = max_y - min_y

    lines = [
        f"Status der Lösung: {_STATUS_LABELS.get(solution.status, solution.status)}",
        f"Grundstück: ca. {solar_w:.1f} m × {solar_h:.1f} m",
        f"Anzahl Geschosse: {program.num_floors}",
        f"Geforderte Wohneinheiten gesamt: {total_requested}",
        f"Platzierte Wohneinheiten: {solution.metrics.num_units_placed}",
        f"Zugewiesene Nutzfläche gesamt: {solution.metrics.total_assigned_area:.1f} m²",
        f"Rechenzeit des Solvers: {solution.solver_time_seconds:.1f} s",
        "Erfüllungsgrad nach Typologie:",
        fulfillment_lines,
    ]
    if solution.message:
        lines.append(f"Hinweis vom Solver: {solution.message}")

    return "\n".join(lines)


def total_requests_for(typology_id: str, program: Program) -> int:
    """Devuelve el número de unidades solicitadas para una tipología concreta."""
    return sum(e.count for e in program.mix if e.typology_id == typology_id)


class SolutionDescription(BaseModel):
    """Resultado de la descripción textual de una Solution."""

    text: str = Field(..., description="Descripción en alemán generada por el LLM")
    language: str = Field(default="de", description="Código ISO 639-1 del idioma de la descripción")
    model_used: str = Field(..., description="Modelo Ollama usado para la generación")


async def describe_solution(
    solution: Solution,
    program: Program,
    solar: Solar,
    client: OllamaClient | None = None,
) -> SolutionDescription:
    """
    Genera una descripción textual en alemán de la solución del solver.

    Usa el modelo de chat configurado (rol ``chat``) con instrucción estricta
    de basarse únicamente en los datos proporcionados y no inventar información.
    Si no se provee un ``client``, crea uno propio y lo cierra al terminar.

    Parámetros
    ----------
    solution:
        Solución del solver a describir.
    program:
        Programa de viviendas del proyecto activo.
    solar:
        Solar del proyecto activo (para dimensiones y área).
    client:
        OllamaClient a usar; si es None se crea uno con la configuración por defecto.
    """
    data_summary = _build_data_summary(solution, program, solar)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Beschreibe das folgende Optimierungsergebnis für den Architekten:\n\n"
                f"{data_summary}"
            ),
        },
    ]

    own_client = client is None
    if own_client:
        client = OllamaClient()

    try:
        response = await client.chat(messages=messages, role="chat")
    finally:
        if own_client:
            await client.aclose()

    return SolutionDescription(
        text=response.content,
        language="de",
        model_used=response.model,
    )


# ---------------------------------------------------------------------------
# Definición Ollama para tool-calling
# ---------------------------------------------------------------------------

DESCRIBE_SOLUTION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "describe_solution",
        "description": (
            "Genera una descripción textual en alemán del resultado del solver para mostrársela "
            "al arquitecto. Incluye el estado, el número de unidades colocadas, el cumplimiento "
            "por tipología y la superficie asignada. "
            "Solo describe datos reales del resultado; no inventa información. "
            "Úsala después de solve_layout para comunicar el resultado al usuario."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}
