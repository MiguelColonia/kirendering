"""Tests del cliente Ollama con un mock HTTP local."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from cimiento.core.config import Settings
from cimiento.llm.client import JsonSchemaResponseFormat, OllamaClient


def _build_settings() -> Settings:
    return Settings(
        ollama_host="http://unused-host:11434",
        ollama_model_reasoning="qwen2.5:14b-instruct-q4_K_M",
        ollama_model_fast="qwen2.5:7b-instruct-q4_K_M",
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
        ollama_model_coder="qwen2.5-coder:7b-instruct-q4_K_M",
    )


def _default_chat_response(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": "2026-04-20T10:00:00Z",
        "message": {"role": "assistant", "content": "mocked response"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 12,
        "eval_count": 7,
    }


@dataclass
class OllamaMockState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    queued_responses: list[dict[str, Any]] = field(default_factory=list)


class OllamaMockHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: OllamaMockState) -> None:
        super().__init__(server_address, OllamaMockHandler)
        self.state = state


class OllamaMockHandler(BaseHTTPRequestHandler):
    server: OllamaMockHTTPServer

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        payload = json.loads(raw_body.decode("utf-8"))
        self.server.state.requests.append(payload)

        response_body = (
            self.server.state.queued_responses.pop(0)
            if self.server.state.queued_responses
            else _default_chat_response(payload["model"])
        )

        encoded_body = json.dumps(response_body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded_body)))
        self.end_headers()
        self.wfile.write(encoded_body)

    def log_message(self, *_: object) -> None:
        return


@dataclass
class OllamaMockServer:
    base_url: str
    state: OllamaMockState
    server: OllamaMockHTTPServer
    thread: threading.Thread

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self.state.requests

    def enqueue_response(self, payload: dict[str, Any]) -> None:
        self.state.queued_responses.append(payload)


@pytest.fixture
def ollama_mock() -> Iterator[OllamaMockServer]:
    state = OllamaMockState()
    server = OllamaMockHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield OllamaMockServer(
            base_url=f"http://127.0.0.1:{server.server_port}",
            state=state,
            server=server,
            thread=thread,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_model_for_role_resolves_models_from_settings() -> None:
    client = OllamaClient(settings=_build_settings())

    assert client.model_for_role("planner") == "qwen2.5:14b-instruct-q4_K_M"
    assert client.model_for_role("validator") == "qwen2.5:14b-instruct-q4_K_M"
    assert client.model_for_role("normative") == "qwen2.5:14b-instruct-q4_K_M"
    assert client.model_for_role("extractor") == "qwen2.5:7b-instruct-q4_K_M"
    assert client.model_for_role("requirements") == "qwen2.5:7b-instruct-q4_K_M"
    assert client.model_for_role("simple") == "qwen2.5:7b-instruct-q4_K_M"
    assert client.model_for_role("chat") == "qwen2.5:7b-instruct-q4_K_M"
    assert client.model_for_role("coder") == "qwen2.5-coder:7b-instruct-q4_K_M"


@pytest.mark.asyncio
async def test_chat_posts_messages_to_local_ollama_mock(ollama_mock: OllamaMockServer) -> None:
    client = OllamaClient(settings=_build_settings(), base_url=ollama_mock.base_url)

    response = await client.chat(
        messages=[
            {"role": "system", "content": "Responde de forma concisa."},
            {"role": "user", "content": "Di hola."},
        ],
        role="chat",
    )

    await client.aclose()

    assert response.model == "qwen2.5:7b-instruct-q4_K_M"
    assert response.content == "mocked response"
    assert len(ollama_mock.requests) == 1
    request_payload = ollama_mock.requests[0]
    assert request_payload["model"] == "qwen2.5:7b-instruct-q4_K_M"
    assert request_payload["stream"] is False
    assert request_payload["messages"][1]["content"] == "Di hola."


@pytest.mark.asyncio
async def test_chat_maps_json_schema_response_format_to_ollama_format(
    ollama_mock: OllamaMockServer,
) -> None:
    client = OllamaClient(settings=_build_settings(), base_url=ollama_mock.base_url)
    response_format = JsonSchemaResponseFormat.model_validate(
        {
            "type": "json_schema",
            "json_schema": {
                "name": "simple_answer",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                    },
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            },
        }
    )

    await client.chat(
        messages=[{"role": "user", "content": "Devuelve JSON válido."}],
        role="validator",
        format=response_format,
    )
    await client.aclose()

    request_payload = ollama_mock.requests[0]
    assert request_payload["model"] == "qwen2.5:14b-instruct-q4_K_M"
    assert request_payload["format"] == {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_chat_forwards_tool_definitions_to_ollama(ollama_mock: OllamaMockServer) -> None:
    client = OllamaClient(settings=_build_settings(), base_url=ollama_mock.base_url)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "resolve_program",
                "description": "Resuelve un programa arquitectónico.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "units": {"type": "integer"},
                    },
                    "required": ["units"],
                },
            },
        }
    ]

    await client.chat(
        messages=[{"role": "user", "content": "Usa la herramienta disponible."}],
        role="planner",
        tools=tools,
    )
    await client.aclose()

    request_payload = ollama_mock.requests[0]
    assert request_payload["model"] == "qwen2.5:14b-instruct-q4_K_M"
    assert request_payload["tools"] == tools
