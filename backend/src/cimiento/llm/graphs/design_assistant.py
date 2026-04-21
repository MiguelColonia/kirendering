"""
Grafo de agentes para el copiloto de anteproyecto residencial.

Implementa un StateGraph de LangGraph con cinco nodos:

  extract_requirements → validate_normative → invoke_solver → interpret_result
                                           ↘                ↘
                                          (errores → END)    handle_infeasible → END

Principio fundamental (CLAUDE.md §3): el LLM nunca resuelve geometría.
Solo extrae intención del usuario, valida contra normativa y comunica resultados.
La geometría y la optimización son responsabilidad exclusiva del solver CP-SAT.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import TypedDict

from cimiento.llm.client import OllamaClient
from cimiento.llm.tools.describe_solution import describe_solution
from cimiento.llm.tools.query_regulation import query_regulation
from cimiento.llm.tools.solve_layout import SolveLayoutInput, SolveLayoutOutput, solve_layout
from cimiento.llm.tools.suggest_typology_adjustments import (
    AdjustmentResult,
    suggest_typology_adjustments,
)
from cimiento.schemas.geometry_primitives import Point2D, Polygon2D
from cimiento.schemas.program import Program, TypologyMix
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import SolutionStatus
from cimiento.schemas.typology import Room, RoomType, Typology

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modelos de datos internos del grafo
# ---------------------------------------------------------------------------


class TypologyEntry(BaseModel):
    """Entrada de tipología extraída del mensaje del usuario."""

    id: str = Field(default="T", description="Código de la tipología, p.ej. T1, T2, T3")
    name: str = Field(default="Wohnung", description="Nombre de la tipología en alemán")
    min_area: float = Field(default=70.0, gt=0.0, description="Área útil mínima en m²")
    count: int = Field(default=1, ge=1, description="Número de unidades deseadas")


class ExtractedDesignParams(BaseModel):
    """Parámetros de diseño extraídos del mensaje del usuario por el LLM."""

    solar_width_m: float | None = Field(
        default=None,
        description="Ancho del solar en metros (null si no mencionado)",
    )
    solar_height_m: float | None = Field(
        default=None,
        description="Profundidad del solar en metros (null si no mencionado)",
    )
    num_floors: int = Field(default=1, ge=1, le=20)
    floor_height_m: float = Field(default=3.0, gt=0.0)
    typology_entries: list[TypologyEntry] = Field(default_factory=list)
    is_complete: bool = Field(
        default=False,
        description=(
            "True solo si solar_width_m, solar_height_m y al menos una tipología "
            "con count >= 1 están presentes"
        ),
    )
    clarification_needed_de: str | None = Field(
        default=None,
        description="Frage an den Benutzer auf Deutsch nach fehlenden Informationen",
    )


class ValidationOutcome(BaseModel):
    """Resultado de la validación normativa."""

    ok: bool = Field(..., description="True si no hay errores bloqueantes")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message_de: str = Field(..., description="Nachricht an den Benutzer auf Deutsch")


# ---------------------------------------------------------------------------
# Estado compartido del grafo
# ---------------------------------------------------------------------------


class DesignAssistantState(TypedDict):
    """Estado compartido entre todos los nodos del grafo."""

    user_message: str
    extracted_params: dict[str, Any] | None
    solution: dict[str, Any] | None
    building: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    user_response_de: str | None
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# Helpers de construcción de schemas BIM desde parámetros extraídos
# ---------------------------------------------------------------------------

_LIVING_AREA_FRACTION = 0.28


def _build_solar(params: ExtractedDesignParams) -> Solar:
    """Construye un Solar rectangular a partir de los parámetros extraídos."""
    w = params.solar_width_m or 20.0
    h = params.solar_height_m or 30.0
    max_height = params.num_floors * params.floor_height_m + 1.5
    return Solar(
        id="extracted-solar",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=w, y=0.0),
                Point2D(x=w, y=h),
                Point2D(x=0.0, y=h),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=max_height,
    )


def _build_program(params: ExtractedDesignParams) -> Program:
    """Construye un Program a partir de las entradas de tipología extraídas."""
    typologies: list[Typology] = []
    mix: list[TypologyMix] = []
    seen_ids: set[str] = set()

    for entry in params.typology_entries:
        tid = entry.id if entry.id not in seen_ids else f"{entry.id}_{len(seen_ids)}"
        seen_ids.add(tid)
        min_area = max(entry.min_area, 30.0)
        living_area = max(min_area * _LIVING_AREA_FRACTION, 10.0)
        typologies.append(
            Typology(
                id=tid,
                name=entry.name,
                min_useful_area=min_area,
                max_useful_area=min_area * 1.35,
                num_bedrooms=max(1, int(min_area / 35)),
                num_bathrooms=1,
                rooms=[Room(type=RoomType.LIVING, min_area=living_area, min_short_side=3.0)],
            )
        )
        mix.append(TypologyMix(typology_id=tid, count=entry.count))

    return Program(
        project_id="assistant-project",
        num_floors=params.num_floors,
        floor_height_m=params.floor_height_m,
        typologies=typologies,
        mix=mix,
    )


# ---------------------------------------------------------------------------
# Prompts del sistema
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """\
Du bist ein Assistent, der Architekturparameter aus Texten auf Deutsch oder Spanisch extrahiert.
Antworte ausschließlich mit einem JSON-Objekt gemäß folgendem Schema:

{
  "solar_width_m": <Zahl oder null>,
  "solar_height_m": <Zahl oder null>,
  "num_floors": <ganze Zahl, Standard 1>,
  "floor_height_m": <Dezimalzahl, Standard 3.0>,
  "typology_entries": [
    {"id": "T2", "name": "Zweizimmerwohnung", "min_area": 70.0, "count": 3}
  ],
  "is_complete": <true wenn Grundstückmaße und mind. 1 Typologie vorhanden>,
  "clarification_needed_de": <Frage auf Deutsch oder null>
}

Regeln:
- Extrahiere Grundstücksmaße in Metern. "20x30" → width=20, height=30.
- Erkenne typische Wohnungsbezeichnungen: T1/1-Zimmer=50m², T2/2-Zimmer=70m², T3/3-Zimmer=90m².
- Wenn Informationen fehlen, setze is_complete=false und formuliere clarification_needed_de.
- Antworte NUR mit dem JSON, ohne Erklärungen."""

_VALIDATE_SYSTEM = """\
Du bist ein Normativprüfer für Wohngebäude in Spanien.
Dir werden Entwurfsparameter und Auszüge aus der Bauordnung übergeben.
Antworte ausschließlich mit einem JSON-Objekt:

{
  "ok": <true wenn keine Fehler>,
  "warnings": ["..."],
  "errors": ["..."],
  "message_de": "<Zusammenfassung auf Deutsch>"
}

Regeln:
- Fehler (errors) blockieren den Entwurf. Warnungen (warnings) sind hinweise.
- Prüfe: Geschosszahl vs. Maximalhöhe, Mindestflächen, fehlende Angaben.
- Antworte NUR mit dem JSON."""


# ---------------------------------------------------------------------------
# Fábrica del grafo
# ---------------------------------------------------------------------------


def build_graph(
    client: OllamaClient | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """
    Construye y compila el grafo del copiloto de anteproyecto.

    Parámetros
    ----------
    client:
        OllamaClient a usar en los nodos LLM. Si es None se crea uno con la
        configuración por defecto.
    checkpointer:
        Checkpointer de LangGraph para persistencia multi-turno.
        Si es None se usa MemorySaver() (en memoria, para la sesión actual).

    Devuelve
    --------
    CompiledStateGraph listo para invocar con ``ainvoke``.
    El llamante debe pasar ``config={"configurable": {"thread_id": "<id>"}}``
    para activar la persistencia multi-turno.
    """
    own_client = client is None
    if own_client:
        client = OllamaClient()

    if checkpointer is None:
        checkpointer = MemorySaver()

    # ------------------------------------------------------------------
    # Nodo 1: extract_requirements
    # ------------------------------------------------------------------

    async def extract_requirements(state: DesignAssistantState) -> dict[str, Any]:
        """
        Extrae parámetros de diseño del mensaje del usuario con qwen2.5:7b.

        Usa output estructurado (format="json") para obtener un ExtractedDesignParams
        validado por Pydantic. Si el mensaje no contiene información suficiente, el
        campo ``is_complete`` será False y ``clarification_needed_de`` contendrá la
        pregunta al usuario.
        """
        messages = [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {"role": "user", "content": state["user_message"]},
        ]
        try:
            response = await client.chat(messages=messages, role="extractor", format="json")
            params = ExtractedDesignParams.model_validate_json(response.content)
        except (ValidationError, ValueError, Exception) as exc:
            log.warning("extract_requirements: fallo al parsear salida del LLM: %s", exc)
            params = ExtractedDesignParams(
                is_complete=False,
                clarification_needed_de=(
                    "Ich konnte Ihre Anfrage nicht verstehen. "
                    "Bitte beschreiben Sie das Grundstück (Breite × Tiefe in Metern) "
                    "und die gewünschten Wohnungstypen mit Anzahl."
                ),
            )

        partial: dict[str, Any] = {
            "extracted_params": params.model_dump(),
            "messages": [{"role": "user", "content": state["user_message"]}],
        }
        if not params.is_complete and params.clarification_needed_de:
            partial["user_response_de"] = params.clarification_needed_de

        return partial

    # ------------------------------------------------------------------
    # Nodo 2: validate_normative
    # ------------------------------------------------------------------

    async def validate_normative(state: DesignAssistantState) -> dict[str, Any]:
        """
        Valida los parámetros extraídos contra la normativa urbanística.

        Obtiene datos normativos relevantes mediante query_regulation y los
        pasa al modelo qwen2.5:14b (rol "normative") junto con los parámetros
        para que evalúe el cumplimiento y devuelva un ValidationOutcome.
        """
        raw = state.get("extracted_params") or {}
        params = ExtractedDesignParams.model_validate(raw)

        # Obtener normativa relevante (determinista, sin LLM)
        reg_height = query_regulation("height")
        reg_habitability = query_regulation("habitability")
        reg_text = "\n".join(
            f"- [{r.code}] {r.description}: {r.value}"
            for r in reg_height.items + reg_habitability.items
        )

        params_summary = (
            f"Grundstück: {params.solar_width_m} m × {params.solar_height_m} m\n"
            f"Geschosse: {params.num_floors}, Geschosshöhe: {params.floor_height_m} m\n"
            f"Maximale Höhe implizit: "
            f"{params.num_floors * params.floor_height_m:.1f} m\n"
            + "\n".join(
                f"Typologie {e.id}: {e.min_area} m², {e.count} Einheiten"
                for e in params.typology_entries
            )
        )

        messages = [
            {"role": "system", "content": _VALIDATE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Normative Anforderungen:\n{reg_text}\n\n"
                    f"Entwurfsparameter:\n{params_summary}"
                ),
            },
        ]
        try:
            response = await client.chat(
                messages=messages, role="normative", format="json"
            )
            outcome = ValidationOutcome.model_validate_json(response.content)
        except (ValidationError, ValueError, Exception) as exc:
            log.warning("validate_normative: fallo al parsear salida del LLM: %s", exc)
            outcome = ValidationOutcome(
                ok=True,
                warnings=["Normativprüfung konnte nicht abgeschlossen werden."],
                message_de="Normativprüfung übersprungen. Entwurf wird fortgesetzt.",
            )

        partial: dict[str, Any] = {"validation_result": outcome.model_dump()}
        if not outcome.ok:
            errors_text = "\n".join(f"• {e}" for e in outcome.errors)
            partial["user_response_de"] = (
                f"Der Entwurf entspricht nicht den normativen Anforderungen:\n"
                f"{errors_text}\n\n{outcome.message_de}"
            )
        return partial

    # ------------------------------------------------------------------
    # Nodo 3: invoke_solver
    # ------------------------------------------------------------------

    async def invoke_solver(state: DesignAssistantState) -> dict[str, Any]:
        """
        Invoca el solver CP-SAT sin LLM.

        Construye Solar y Program desde extracted_params y llama a solve_layout.
        El LLM no interviene en ningún cálculo geométrico.
        """
        raw = state.get("extracted_params") or {}
        params = ExtractedDesignParams.model_validate(raw)
        solar = _build_solar(params)
        program = _build_program(params)

        result: SolveLayoutOutput = solve_layout(
            SolveLayoutInput(solar=solar, program=program, timeout_seconds=60)
        )
        return {"solution": result.model_dump(mode="json")}

    # ------------------------------------------------------------------
    # Nodo 4: interpret_result
    # ------------------------------------------------------------------

    async def interpret_result(state: DesignAssistantState) -> dict[str, Any]:
        """
        Genera la descripción en alemán de la solución para el usuario.

        Reconstruye los objetos BIM desde el estado y delega en describe_solution
        (qwen2.5:7b, rol "chat") para producir el texto final.
        """
        raw_params = state.get("extracted_params") or {}
        raw_solution = state.get("solution") or {}
        params = ExtractedDesignParams.model_validate(raw_params)
        solar = _build_solar(params)
        program = _build_program(params)

        solution_output = SolveLayoutOutput.model_validate(raw_solution)
        description = await describe_solution(
            solution=solution_output.solution,
            program=program,
            solar=solar,
            client=client,
        )
        return {
            "user_response_de": description.text,
            "messages": [{"role": "assistant", "content": description.text}],
        }

    # ------------------------------------------------------------------
    # Nodo 5: handle_infeasible
    # ------------------------------------------------------------------

    async def handle_infeasible(state: DesignAssistantState) -> dict[str, Any]:
        """
        Rama para soluciones infactibles: propone ajustes deterministas al programa.

        Llama a suggest_typology_adjustments (sin LLM) y formatea las sugerencias
        en un mensaje en alemán para el usuario, esperando confirmación en el
        siguiente turno de la conversación.
        """
        raw_params = state.get("extracted_params") or {}
        raw_solution = state.get("solution") or {}
        params = ExtractedDesignParams.model_validate(raw_params)
        program = _build_program(params)
        solution_output = SolveLayoutOutput.model_validate(raw_solution)
        adjustment: AdjustmentResult = suggest_typology_adjustments(
            program=program,
            solution=solution_output.solution,
        )

        if not adjustment.suggestions:
            message = (
                f"Die Optimierung hat kein Ergebnis geliefert "
                f"(Status: {solution_output.status}). "
                f"Diagnose: {adjustment.explanation}"
            )
        else:
            lines = [
                "Die Raumverteilung konnte mit dem aktuellen Programm nicht gelöst werden.",
                f"Diagnose: {adjustment.explanation}",
                "",
                "Mögliche Anpassungen:",
            ]
            for i, suggestion in enumerate(adjustment.suggestions, 1):
                new_total = sum(e.count for e in suggestion.adjusted_program.mix)
                lines.append(f"{i}. {suggestion.reason} ({new_total} Einheiten gesamt)")
                lines.append(f"   → {suggestion.impact_summary}")
            lines.append("")
            lines.append(
                "Möchten Sie eine dieser Anpassungen übernehmen? "
                "Antworten Sie mit der Nummer der gewünschten Option."
            )
            message = "\n".join(lines)

        return {
            "user_response_de": message,
            "messages": [{"role": "assistant", "content": message}],
        }

    # ------------------------------------------------------------------
    # Funciones de enrutamiento condicional
    # ------------------------------------------------------------------

    def _route_after_extraction(state: DesignAssistantState) -> str:
        """Procede a validación solo si la extracción fue completa."""
        raw = state.get("extracted_params") or {}
        if not raw.get("is_complete", False):
            return END
        return "validate_normative"

    def _route_after_validation(state: DesignAssistantState) -> str:
        """Procede al solver solo si la validación normativa no tiene errores."""
        raw = state.get("validation_result") or {}
        if not raw.get("ok", True):
            return END
        return "invoke_solver"

    def _route_after_solver(state: DesignAssistantState) -> str:
        """Deriva a handle_infeasible si el solver no encontró solución factible."""
        raw = state.get("solution") or {}
        status = raw.get("status", "ERROR")
        if status in (
            SolutionStatus.INFEASIBLE,
            SolutionStatus.TIMEOUT,
            SolutionStatus.ERROR,
        ):
            return "handle_infeasible"
        return "interpret_result"

    # ------------------------------------------------------------------
    # Construcción del grafo
    # ------------------------------------------------------------------

    builder = StateGraph(DesignAssistantState)

    builder.add_node("extract_requirements", extract_requirements)
    builder.add_node("validate_normative", validate_normative)
    builder.add_node("invoke_solver", invoke_solver)
    builder.add_node("interpret_result", interpret_result)
    builder.add_node("handle_infeasible", handle_infeasible)

    builder.add_edge(START, "extract_requirements")
    builder.add_conditional_edges(
        "extract_requirements",
        _route_after_extraction,
        {"validate_normative": "validate_normative", END: END},
    )
    builder.add_conditional_edges(
        "validate_normative",
        _route_after_validation,
        {"invoke_solver": "invoke_solver", END: END},
    )
    builder.add_conditional_edges(
        "invoke_solver",
        _route_after_solver,
        {"interpret_result": "interpret_result", "handle_infeasible": "handle_infeasible"},
    )
    builder.add_edge("interpret_result", END)
    builder.add_edge("handle_infeasible", END)

    return builder.compile(checkpointer=checkpointer)
