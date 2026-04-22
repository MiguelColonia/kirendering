"""
Tests de fidelidad del nodo answer_with_regulation.

Verifican que:
1. El retriever devuelve el chunk correcto dado un Qdrant mock con payload conocido.
2. El nodo construye el contexto RAG correctamente y lo pasa al LLM.
3. El prompt del sistema contiene las instrucciones de cita obligatorias.
4. El enrutador clasifica correctamente consultas normativas vs. peticiones de diseño.
5. La respuesta del nodo se almacena en user_response_de y en messages.

Los tests usan AsyncMock para Qdrant y Ollama; el LLM nunca se invoca realmente.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cimiento.llm.graphs.design_assistant import _is_regulation_query, build_graph
from cimiento.rag.retriever import format_chunks_for_llm, retrieve
from cimiento.rag.schemas import RegulationChunk, RegulationSearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scored_point(
    chunk_id: str,
    score: float,
    document: str = "GEG",
    article_number: str = "§ 10",
    article_title: str = "Anforderungen an zu errichtende Wohngebäude",
    text: str = (
        "Der Jahres-Primärenergiebedarf eines zu errichtenden Wohngebäudes "
        "darf einen Höchstwert von 55 kWh/(m²·a) nicht überschreiten."
    ),
    section: str = "Abschnitt 2",
) -> MagicMock:
    point = MagicMock()
    point.id = chunk_id
    point.score = score
    point.payload = {
        "document": document,
        "section": section,
        "article_number": article_number,
        "article_title": article_title,
        "text": text,
    }
    return point


# ---------------------------------------------------------------------------
# Tests del clasificador de intención
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Was sagt § 10 GEG über den Primärenergiebedarf?", True),
        ("Welche Anforderungen stellt das GEG?", True),
        ("Wie hoch ist die Aufzugspflicht nach MBO?", True),
        ("Erkläre mir BauNVO § 17", True),
        ("WoFlV Mindestfläche Wohnung", True),
        ("Plane ein Grundstück 20x30 mit 4 Wohnungen", False),
        ("Ich möchte ein 15×20 Grundstück bebauen", False),
        ("3 Wohnungen auf 800 m²", False),
        ("Wie viele Stockwerke kann ich bauen?", False),
        ("Guten Morgen, ich brauche Hilfe", False),
    ],
)
def test_is_regulation_query(message: str, expected: bool) -> None:
    """_is_regulation_query clasifica correctamente las consultas."""
    assert _is_regulation_query(message) is expected


# ---------------------------------------------------------------------------
# Tests del retriever (fidelidad del chunk recuperado)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retriever_returns_correct_article_number() -> None:
    """El retriever devuelve el artículo exacto que Qdrant reporta."""
    mock_ollama = AsyncMock()
    mock_ollama.embed.return_value = [[0.1] * 768]

    mock_qdrant = AsyncMock()
    mock_qdrant.search.return_value = [
        _make_scored_point("uuid-geg-10", 0.94, document="GEG", article_number="§ 10")
    ]

    results = await retrieve(
        query="Primärenergiebedarf Neubau GEG",
        ollama_client=mock_ollama,
        qdrant_client=mock_qdrant,
        collection_name="normativa",
        k=5,
    )

    assert len(results) == 1
    assert results[0].chunk.document == "GEG"
    assert results[0].chunk.article_number == "§ 10"
    assert results[0].score == pytest.approx(0.94)


@pytest.mark.asyncio
async def test_retriever_preserves_chunk_text() -> None:
    """El texto del chunk se transfiere íntegro desde el payload de Qdrant."""
    expected_text = "Der Höchstwert beträgt 55 kWh/(m²·a) gemäß Anlage 1 Tabelle 1."
    mock_ollama = AsyncMock()
    mock_ollama.embed.return_value = [[0.0] * 768]
    mock_qdrant = AsyncMock()
    mock_qdrant.search.return_value = [_make_scored_point("uuid-1", 0.88, text=expected_text)]

    results = await retrieve(
        query="Primärenergiebedarf",
        ollama_client=mock_ollama,
        qdrant_client=mock_qdrant,
        collection_name="normativa",
    )

    assert results[0].chunk.text == expected_text


@pytest.mark.asyncio
async def test_retriever_passes_query_text_to_embed() -> None:
    """El texto de la consulta se pasa sin modificar al cliente de embeddings."""
    mock_ollama = AsyncMock()
    mock_ollama.embed.return_value = [[0.0] * 768]
    mock_qdrant = AsyncMock()
    mock_qdrant.search.return_value = []

    query = "Mindesthöhe Aufenthaltsraum MBO § 2"
    await retrieve(
        query=query,
        ollama_client=mock_ollama,
        qdrant_client=mock_qdrant,
        collection_name="normativa",
    )

    mock_ollama.embed.assert_called_once_with(query)


# ---------------------------------------------------------------------------
# Tests del formateador de contexto (para el LLM)
# ---------------------------------------------------------------------------


def test_format_chunks_includes_document_and_article() -> None:
    """format_chunks_for_llm incluye el documento y el número de artículo."""
    chunk = RegulationChunk(
        id=RegulationChunk.make_id("GEG", "§ 10"),
        document="GEG",
        section="Abschnitt 2",
        article_number="§ 10",
        article_title="Anforderungen an zu errichtende Wohngebäude",
        text="Der Jahres-Primärenergiebedarf darf 55 kWh/(m²·a) nicht überschreiten.",
    )
    result = RegulationSearchResult(chunk=chunk, score=0.94)
    context = format_chunks_for_llm([result])

    assert "[GEG § 10]" in context
    assert "Primärenergiebedarf" in context


def test_format_chunks_citable_reference_format() -> None:
    """El contexto formateado sigue el patrón [DOC §N] que el prompt del sistema exige."""
    chunk = RegulationChunk(
        id=RegulationChunk.make_id("MBO", "§ 37"),
        document="MBO",
        section="Abschnitt 5",
        article_number="§ 37",
        article_title="Aufzüge",
        text="Aufzüge sind in Gebäuden mit mehr als vier Vollgeschossen erforderlich.",
    )
    result = RegulationSearchResult(chunk=chunk, score=0.91)
    context = format_chunks_for_llm([result])

    assert "[MBO § 37]" in context
    assert "Aufzüge" in context


# ---------------------------------------------------------------------------
# Infraestructura de mock HTTP para tests del grafo
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
            body = {"model": payload["model"], "created_at": "2026-04-21T10:00:00Z"}

        if self.path == "/api/embed":
            body.setdefault("embeddings", [[0.1] * 768])
            body.setdefault("model", payload.get("model", "nomic-embed-text"))
        elif self.path == "/api/chat":
            body.setdefault(
                "message",
                {
                    "role": "assistant",
                    "content": (
                        "Gemäß den bereitgestellten Normdokumenten gilt: "
                        "Der Jahres-Primärenergiebedarf darf 55 kWh/(m²·a) "
                        "nicht überschreiten [GEG § 10]."
                    ),
                },
            )
            body.setdefault("done", True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        body_bytes = json.dumps(body).encode()
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *_: Any) -> None:
        pass


@pytest.fixture()
def mock_http_server() -> Iterator[tuple[str, MockState]]:
    state = MockState()
    server = MockHTTPServer(("127.0.0.1", 0), state)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", state
    server.shutdown()


# ---------------------------------------------------------------------------
# Tests del nodo answer_with_regulation (integración con grafo)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answer_with_regulation_routed_for_paragraph_query(
    mock_http_server: tuple[str, MockState],
) -> None:
    """Consultas con § se enrutan a answer_with_regulation y producen user_response_de."""
    from cimiento.core.config import Settings
    from cimiento.llm.client import OllamaClient

    base_url, state = mock_http_server

    settings = Settings(
        ollama_host=base_url,
        ollama_model_chat="qwen2.5:7b",
        ollama_model_reasoning="qwen2.5:14b",
        ollama_model_embed="nomic-embed-text",
    )
    client = OllamaClient(settings=settings)
    graph = build_graph(client=client, qdrant_client=None)

    result = await graph.ainvoke(
        {"user_message": "Was sagt § 10 GEG über den Primärenergiebedarf von Neubauten?"},
        config={"configurable": {"thread_id": "fidelity-test-1"}},
    )

    assert result["user_response_de"] is not None
    assert len(result["user_response_de"]) > 0


@pytest.mark.asyncio
async def test_answer_with_regulation_system_prompt_contains_citation_rules(
    mock_http_server: tuple[str, MockState],
) -> None:
    """El prompt del sistema enviado al LLM exige el formato de cita [DOC §N]."""
    from cimiento.core.config import Settings
    from cimiento.llm.client import OllamaClient

    base_url, state = mock_http_server

    settings = Settings(
        ollama_host=base_url,
        ollama_model_chat="qwen2.5:7b",
        ollama_model_reasoning="qwen2.5:14b",
        ollama_model_embed="nomic-embed-text",
    )
    client = OllamaClient(settings=settings)
    graph = build_graph(client=client, qdrant_client=None)

    await graph.ainvoke(
        {"user_message": "Welche Anforderungen stellt GEG § 10 an Neubauten?"},
        config={"configurable": {"thread_id": "fidelity-test-2"}},
    )

    # Buscar la llamada a /api/chat (ignorar /api/embed del mock context)
    chat_requests = [r for r in state.requests if "messages" in r]
    assert chat_requests, "El nodo debe haber llamado al LLM"

    system_messages = [
        msg["content"]
        for r in chat_requests
        for msg in r.get("messages", [])
        if msg.get("role") == "system"
    ]
    assert system_messages, "Debe haber un mensaje de sistema"
    system_text = " ".join(system_messages)

    assert "AUSSCHLIESSLICH" in system_text or "ausschließlich" in system_text.lower()
    assert "[GEG §N]" in system_text or "[GEG" in system_text
    assert "[MBO §N]" in system_text or "[MBO" in system_text


@pytest.mark.asyncio
async def test_answer_with_regulation_context_contains_chunk_text(
    mock_http_server: tuple[str, MockState],
) -> None:
    """El texto del chunk RAG (mock) aparece en el prompt de usuario enviado al LLM."""
    from cimiento.core.config import Settings
    from cimiento.llm.client import OllamaClient

    base_url, state = mock_http_server

    settings = Settings(
        ollama_host=base_url,
        ollama_model_chat="qwen2.5:7b",
        ollama_model_reasoning="qwen2.5:14b",
        ollama_model_embed="nomic-embed-text",
    )
    client = OllamaClient(settings=settings)
    # Sin Qdrant: el nodo usa _mock_regulation_context
    graph = build_graph(client=client, qdrant_client=None)

    await graph.ainvoke(
        {"user_message": "Was sagt GEG über den Primärenergiebedarf?"},
        config={"configurable": {"thread_id": "fidelity-test-3"}},
    )

    chat_requests = [r for r in state.requests if "messages" in r]
    user_messages = [
        msg["content"]
        for r in chat_requests
        for msg in r.get("messages", [])
        if msg.get("role") == "user"
    ]
    combined = " ".join(user_messages)

    # El contexto mock incluye datos de GEG (energía)
    assert "GEG" in combined or "Primärenergie" in combined or "kWh" in combined


@pytest.mark.asyncio
async def test_design_request_not_routed_to_regulation_node(
    mock_http_server: tuple[str, MockState],
) -> None:
    """Una petición de diseño con dimensiones va a extract_requirements, no al nodo normativo."""
    from cimiento.core.config import Settings
    from cimiento.llm.client import OllamaClient

    base_url, state = mock_http_server

    # La respuesta de extract_requirements debe indicar parámetros incompletos
    state.queued_responses = [
        {
            "model": "qwen2.5:7b",
            "created_at": "2026-04-21T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "solar_width_m": None,
                        "solar_height_m": None,
                        "num_floors": 1,
                        "floor_height_m": 3.0,
                        "typology_entries": [],
                        "is_complete": False,
                        "clarification_needed_de": "Bitte geben Sie die Grundstücksmaße an.",
                    }
                ),
            },
            "done": True,
        }
    ]

    settings = Settings(
        ollama_host=base_url,
        ollama_model_chat="qwen2.5:7b",
        ollama_model_reasoning="qwen2.5:14b",
        ollama_model_embed="nomic-embed-text",
    )
    client = OllamaClient(settings=settings)
    graph = build_graph(client=client, qdrant_client=None)

    result = await graph.ainvoke(
        {"user_message": "Ich möchte ein 20x30 Grundstück mit 3 Wohnungen planen"},
        config={"configurable": {"thread_id": "fidelity-test-4"}},
    )

    chat_requests = [r for r in state.requests if "messages" in r]
    # El primer request al LLM debe tener el system prompt de extracción (no de normativa)
    first_system = next(
        (
            msg["content"]
            for msg in chat_requests[0].get("messages", [])
            if msg.get("role") == "system"
        ),
        "",
    )
    assert "JSON" in first_system  # _EXTRACT_SYSTEM siempre pide JSON
    assert "AUSSCHLIESSLICH" not in first_system  # no es el prompt normativo
    assert result.get("extracted_params") is not None
