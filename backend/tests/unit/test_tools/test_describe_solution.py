"""Tests del tool describe_solution con mock HTTP de Ollama."""

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
from cimiento.llm.tools.describe_solution import SolutionDescription, describe_solution
from cimiento.schemas import (
    Point2D,
    Polygon2D,
    Program,
    Room,
    RoomType,
    Solar,
    Typology,
    TypologyMix,
)
from cimiento.schemas.solution import Solution, SolutionMetrics, SolutionStatus

# ---------------------------------------------------------------------------
# Mock HTTP server (misma infraestructura que test_ollama_client.py)
# ---------------------------------------------------------------------------


@dataclass
class MockState:
    requests: list[dict[str, Any]] = field(default_factory=list)
    queued_responses: list[dict[str, Any]] = field(default_factory=list)


class MockHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: MockState) -> None:
        super().__init__(server_address, MockHandler)
        self.state = state


class MockHandler(BaseHTTPRequestHandler):
    server: MockHTTPServer

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length))
        self.server.state.requests.append(payload)
        response = (
            self.server.state.queued_responses.pop(0)
            if self.server.state.queued_responses
            else {
                "model": payload["model"],
                "created_at": "2026-04-20T10:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": "Die Lösung ist OPTIMAL. Es wurden 3 Wohneinheiten platziert.",
                },
                "done": True,
            }
        )
        encoded = json.dumps(response).encode()
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

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self.state.requests


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


# ---------------------------------------------------------------------------
# Fixtures de dominio
# ---------------------------------------------------------------------------


@pytest.fixture
def solar() -> Solar:
    return Solar(
        id="s1",
        contour=Polygon2D(points=[
            Point2D(x=0, y=0), Point2D(x=20, y=0),
            Point2D(x=20, y=30), Point2D(x=0, y=30),
        ]),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )


@pytest.fixture
def program() -> Program:
    return Program(
        project_id="p1", num_floors=1, floor_height_m=3.0,
        typologies=[
            Typology(
                id="T2", name="Zweizimmerwohnung",
                min_useful_area=70.0, max_useful_area=90.0,
                num_bedrooms=2, num_bathrooms=1,
                rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5)],
            )
        ],
        mix=[TypologyMix(typology_id="T2", count=3)],
    )


@pytest.fixture
def solution_optimal() -> Solution:
    return Solution(
        status=SolutionStatus.OPTIMAL,
        placements=[],
        communication_cores=[],
        metrics=SolutionMetrics(
            total_assigned_area=210.0,
            num_units_placed=3,
            typology_fulfillment={"T2": 1.0},
        ),
        solver_time_seconds=2.5,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_describe_solution_returns_description(
    ollama_mock: MockServer,
    solution_optimal: Solution,
    program: Program,
    solar: Solar,
) -> None:
    settings = Settings(
        ollama_host=ollama_mock.base_url,
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    async with OllamaClient(settings=settings) as client:
        result = await describe_solution(solution_optimal, program, solar, client=client)

    assert isinstance(result, SolutionDescription)
    assert len(result.text) > 10
    assert result.language == "de"


@pytest.mark.asyncio
async def test_describe_solution_uses_chat_role(
    ollama_mock: MockServer,
    solution_optimal: Solution,
    program: Program,
    solar: Solar,
) -> None:
    settings = Settings(
        ollama_host=ollama_mock.base_url,
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    async with OllamaClient(settings=settings) as client:
        await describe_solution(solution_optimal, program, solar, client=client)

    assert len(ollama_mock.requests) == 1
    assert ollama_mock.requests[0]["model"] == "qwen2.5:7b-instruct-q4_K_M"


@pytest.mark.asyncio
async def test_describe_solution_system_prompt_in_german(
    ollama_mock: MockServer,
    solution_optimal: Solution,
    program: Program,
    solar: Solar,
) -> None:
    settings = Settings(
        ollama_host=ollama_mock.base_url,
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    async with OllamaClient(settings=settings) as client:
        await describe_solution(solution_optimal, program, solar, client=client)

    messages = ollama_mock.requests[0]["messages"]
    system_msg = next(m for m in messages if m["role"] == "system")
    assert "Deutsch" in system_msg["content"]


@pytest.mark.asyncio
async def test_describe_solution_user_prompt_contains_data(
    ollama_mock: MockServer,
    solution_optimal: Solution,
    program: Program,
    solar: Solar,
) -> None:
    """El prompt de usuario incluye datos reales de la solución (no inventados)."""
    settings = Settings(
        ollama_host=ollama_mock.base_url,
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    async with OllamaClient(settings=settings) as client:
        await describe_solution(solution_optimal, program, solar, client=client)

    messages = ollama_mock.requests[0]["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "OPTIMAL" in user_msg["content"]
    assert "3" in user_msg["content"]   # num_units_placed


@pytest.mark.asyncio
async def test_describe_solution_model_name_in_result(
    ollama_mock: MockServer,
    solution_optimal: Solution,
    program: Program,
    solar: Solar,
) -> None:
    settings = Settings(
        ollama_host=ollama_mock.base_url,
        ollama_model_chat="qwen2.5:7b-instruct-q4_K_M",
    )
    async with OllamaClient(settings=settings) as client:
        result = await describe_solution(solution_optimal, program, solar, client=client)

    assert result.model_used == "qwen2.5:7b-instruct-q4_K_M"
