"""
Tests del grafo design_assistant con mocks de LLM.

Se cubren cuatro caminos de ejecución:
1. Happy path: extracción completa → validación OK → solver OPTIMAL → descripción.
2. Extraction incompleta: el LLM no extrae parámetros suficientes → END con clarificación.
3. Validation error: LLM detecta violación normativa → END con mensaje de error.
4. Infeasible: solver no encuentra solución → handle_infeasible con sugerencias.

El mock HTTP sirve respuestas con cola FIFO. Los nodos que llaman al solver (invoke_solver)
son puramente deterministas y usan el solver CP-SAT real.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from cimiento.core.config import Settings
from cimiento.llm.client import OllamaClient
from cimiento.llm.graphs.design_assistant import build_graph

# ---------------------------------------------------------------------------
# Infraestructura de mock HTTP (reutiliza patrón de test_ollama_client.py)
# ---------------------------------------------------------------------------


@dataclass
class MockState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    queued_responses: list[dict[str, Any]] = field(default_factory=list)


class MockHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple[str, int], state: MockState) -> None:
        super().__init__(addr, MockHandler)
        self.state = state


class MockHandler(BaseHTTPRequestHandler):
    server: MockHTTPServer

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.server.state.requests.append(payload)

        if self.server.state.queued_responses:
            body = self.server.state.queued_responses.pop(0)
        else:
            body = {
                "model": payload["model"],
                "created_at": "2026-04-20T10:00:00Z",
                "message": {"role": "assistant", "content": "{}"},
                "done": True,
            }
        encoded = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_: object) -> None:
        return


@dataclass
class MockServer:
    base_url: str
    state: MockState
    _server: MockHTTPServer
    _thread: threading.Thread

    def enqueue(self, content: str, model: str = "qwen2.5:7b-instruct-q4_K_M") -> None:
        self.state.queued_responses.append(
            {
                "model": model,
                "created_at": "2026-04-20T10:00:00Z",
                "message": {"role": "assistant", "content": content},
                "done": True,
            }
        )

    @property
    def call_count(self) -> int:
        return len(self.state.requests)


@pytest.fixture
def ollama_mock() -> Iterator[MockServer]:
    state = MockState()
    server = MockHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield MockServer(
            base_url=f"http://127.0.0.1:{server.server_port}",
            state=state,
            _server=server,
            _thread=thread,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _make_graph(mock: MockServer) -> Any:
    settings = Settings(
        ollama_host=mock.base_url,
        ollama_model_fast="qwen2.5:7b-instruct-q4_K_M",
        ollama_model_reasoning="qwen2.5:14b-instruct-q4_K_M",
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    client = OllamaClient(settings=settings)
    return build_graph(client=client), client


# ---------------------------------------------------------------------------
# Payloads de respuesta reutilizables
# ---------------------------------------------------------------------------

_PARAMS_COMPLETE = json.dumps(
    {
        "solar_width_m": 20.0,
        "solar_height_m": 30.0,
        "num_floors": 1,
        "floor_height_m": 3.0,
        "typology_entries": [
            {"id": "T2", "name": "Zweizimmerwohnung", "min_area": 70.0, "count": 2}
        ],
        "is_complete": True,
        "clarification_needed_de": None,
    }
)

_PARAMS_INCOMPLETE = json.dumps(
    {
        "solar_width_m": None,
        "solar_height_m": None,
        "num_floors": 1,
        "floor_height_m": 3.0,
        "typology_entries": [],
        "is_complete": False,
        "clarification_needed_de": (
            "Bitte geben Sie die Grundstücksmaße (Breite × Tiefe in Metern) an."
        ),
    }
)

_PARAMS_TINY_SOLAR = json.dumps(
    {
        "solar_width_m": 4.0,
        "solar_height_m": 4.0,
        "num_floors": 1,
        "floor_height_m": 3.0,
        "typology_entries": [
            {"id": "T2", "name": "Zweizimmerwohnung", "min_area": 70.0, "count": 2}
        ],
        "is_complete": True,
        "clarification_needed_de": None,
    }
)

_VALIDATION_OK = json.dumps(
    {
        "ok": True,
        "warnings": [],
        "errors": [],
        "message_de": "Die Parameter entsprechen den normativen Anforderungen.",
    }
)

_VALIDATION_ERROR = json.dumps(
    {
        "ok": False,
        "warnings": [],
        "errors": ["Die Geschosszahl überschreitet die zulässige Gebäudehöhe."],
        "message_de": (
            "Der Entwurf kann nicht realisiert werden: Die maximale Gebäudehöhe wird überschritten."
        ),
    }
)

_DESCRIPTION_DE = "Die Lösung ist optimal. Es wurden 2 Wohneinheiten platziert."


# ---------------------------------------------------------------------------
# Test 1: Happy path — extracción completa → validación OK → OPTIMAL → descripción
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_reaches_interpret_result(ollama_mock: MockServer) -> None:
    """
    El flujo completo produce user_response_de con la descripción en alemán.
    Camino: extract → validate → solver → interpret_result → END.
    """
    graph, client = _make_graph(ollama_mock)

    # 1. extract_requirements: devuelve parámetros completos
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    # 2. validate_normative: sin errores
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
    # 3. describe_solution (dentro de interpret_result)
    ollama_mock.enqueue(_DESCRIPTION_DE)

    try:
        result = await graph.ainvoke(
            {"user_message": "20x30m Grundstück, 2 T2-Wohnungen, 1 Stockwerk"},
            config={"configurable": {"thread_id": "test-happy"}},
        )
    finally:
        await client.aclose()

    assert result["user_response_de"] is not None
    assert result["solution"] is not None
    assert result["solution"]["status"] in ("OPTIMAL", "FEASIBLE")
    assert result["solution"]["num_units_placed"] == 2
    assert result["extracted_params"]["is_complete"] is True


@pytest.mark.asyncio
async def test_happy_path_llm_called_three_times(ollama_mock: MockServer) -> None:
    """El grafo llama al LLM exactamente 3 veces en el happy path."""
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
    ollama_mock.enqueue(_DESCRIPTION_DE)

    try:
        await graph.ainvoke(
            {"user_message": "20x30m, 2 T2-Wohnungen"},
            config={"configurable": {"thread_id": "test-llm-calls"}},
        )
    finally:
        await client.aclose()

    assert ollama_mock.call_count == 3


# ---------------------------------------------------------------------------
# Test 2: Extracción incompleta → END con clarificación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incomplete_extraction_ends_with_clarification(ollama_mock: MockServer) -> None:
    """
    Si el mensaje no contiene suficiente información, el grafo termina en END
    después de extract_requirements con una pregunta de aclaración.
    """
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_INCOMPLETE)

    try:
        result = await graph.ainvoke(
            {"user_message": "Wie viele Wohnungen passen rein?"},
            config={"configurable": {"thread_id": "test-incomplete"}},
        )
    finally:
        await client.aclose()

    assert result["user_response_de"] is not None
    assert "Grundstück" in result["user_response_de"] or "Maß" in result["user_response_de"]
    # El solver nunca debería haberse ejecutado
    assert result.get("solution") is None


@pytest.mark.asyncio
async def test_incomplete_extraction_calls_llm_once(ollama_mock: MockServer) -> None:
    """Con extracción incompleta el LLM se llama exactamente 1 vez."""
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_INCOMPLETE)

    try:
        await graph.ainvoke(
            {"user_message": "Hilfe"},
            config={"configurable": {"thread_id": "test-incomplete-count"}},
        )
    finally:
        await client.aclose()

    assert ollama_mock.call_count == 1


# ---------------------------------------------------------------------------
# Test 3: Error de validación normativa → END con mensaje de error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_error_ends_before_solver(ollama_mock: MockServer) -> None:
    """
    Si validate_normative detecta errores, el grafo termina antes de llamar
    al solver. user_response_de contiene la descripción del error en alemán.
    """
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    ollama_mock.enqueue(_VALIDATION_ERROR, model="qwen2.5:14b-instruct-q4_K_M")

    try:
        result = await graph.ainvoke(
            {"user_message": "20x30m, 20 Stockwerke, 2 T2-Wohnungen"},
            config={"configurable": {"thread_id": "test-validation-error"}},
        )
    finally:
        await client.aclose()

    assert result["validation_result"]["ok"] is False
    assert result.get("solution") is None
    assert result["user_response_de"] is not None
    # El mensaje debe incluir el error normativo
    assert result["user_response_de"] != ""


@pytest.mark.asyncio
async def test_validation_error_calls_llm_twice(ollama_mock: MockServer) -> None:
    """Con error de validación el LLM se llama exactamente 2 veces."""
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    ollama_mock.enqueue(_VALIDATION_ERROR, model="qwen2.5:14b-instruct-q4_K_M")

    try:
        await graph.ainvoke(
            {"user_message": "20x30m, 20 Stockwerke"},
            config={"configurable": {"thread_id": "test-validation-count"}},
        )
    finally:
        await client.aclose()

    assert ollama_mock.call_count == 2


# ---------------------------------------------------------------------------
# Test 4: Solver INFEASIBLE → handle_infeasible con sugerencias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infeasible_solver_routes_to_handle_infeasible(ollama_mock: MockServer) -> None:
    """
    Solar demasiado pequeño (4×4 m) para tipología T2 (70 m²) → INFEASIBLE.
    El grafo deriva a handle_infeasible y produce sugerencias de ajuste.
    """
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_TINY_SOLAR)
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
    # No se encola respuesta para interpret_result porque no debería alcanzarse

    try:
        result = await graph.ainvoke(
            {"user_message": "4x4m Grundstück, 2 T2-Wohnungen"},
            config={"configurable": {"thread_id": "test-infeasible"}},
        )
    finally:
        await client.aclose()

    assert result["solution"]["status"] == "INFEASIBLE"
    assert result["user_response_de"] is not None
    # El mensaje debe contener información sobre el problema o las sugerencias
    assert len(result["user_response_de"]) > 20


@pytest.mark.asyncio
async def test_infeasible_calls_llm_twice_not_three(ollama_mock: MockServer) -> None:
    """Con INFEASIBLE el grafo llama al LLM 2 veces (extract + validate), no 3."""
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_TINY_SOLAR)
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")

    try:
        await graph.ainvoke(
            {"user_message": "4x4m, 2 T2"},
            config={"configurable": {"thread_id": "test-infeasible-count"}},
        )
    finally:
        await client.aclose()

    assert ollama_mock.call_count == 2


# ---------------------------------------------------------------------------
# Test 5: Verificación de edges condicionales con estado inyectado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conditional_edge_validation_ok_routes_to_solver(ollama_mock: MockServer) -> None:
    """validation_result.ok=True → el grafo llega a invoke_solver."""
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
    ollama_mock.enqueue(_DESCRIPTION_DE)

    try:
        result = await graph.ainvoke(
            {"user_message": "20x30m, 2 T2"},
            config={"configurable": {"thread_id": "test-edge-ok"}},
        )
    finally:
        await client.aclose()

    assert result["solution"] is not None
    assert result["validation_result"]["ok"] is True


@pytest.mark.asyncio
async def test_state_persists_across_turns(ollama_mock: MockServer) -> None:
    """
    Con MemorySaver, el estado del primer turno persiste en el segundo turno.
    El segundo ainvoke con el mismo thread_id ve los datos del primero.
    """
    graph, client = _make_graph(ollama_mock)
    ollama_mock.enqueue(_PARAMS_COMPLETE)
    ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
    ollama_mock.enqueue(_DESCRIPTION_DE)

    config = {"configurable": {"thread_id": "test-memory"}}
    try:
        result1 = await graph.ainvoke(
            {"user_message": "20x30m, 2 T2-Wohnungen"},
            config=config,
        )
        # Segundo turno: el estado acumula
        ollama_mock.enqueue(_PARAMS_COMPLETE)
        ollama_mock.enqueue(_VALIDATION_OK, model="qwen2.5:14b-instruct-q4_K_M")
        ollama_mock.enqueue(_DESCRIPTION_DE)
        result2 = await graph.ainvoke(
            {"user_message": "Und mit 3 Stockwerken?"},
            config=config,
        )
    finally:
        await client.aclose()

    # Ambos turnos producen una respuesta
    assert result1["user_response_de"] is not None
    assert result2["user_response_de"] is not None
    # Los mensajes acumulan (multi-turno)
    assert len(result2.get("messages", [])) > len(result1.get("messages", []))
