"""Tests E2E básicos de la API REST y WebSocket."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cimiento.api.main import create_app
from cimiento.schemas import Program, Typology, TypologyMix

pytest_plugins = ["tests.fixtures.valid_cases"]


async def _ok(_: object) -> dict[str, str]:
    return {"status": "ok"}


@pytest.fixture
def client(tmp_path) -> TestClient:
    app = create_app(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api-test.db'}",
        output_root=tmp_path / "outputs",
        health_checks={"ollama": _ok, "qdrant": _ok},
    )
    with TestClient(app) as client:
        yield client


def _project_payload(sample_solar_rectangular, sample_typology_t2: Typology) -> dict:
    program = Program(
        project_id="temporary-client-project",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )
    return {
        "name": "Wohnprojekt Test",
        "description": "Projekt für API-Tests",
        "solar": sample_solar_rectangular.model_dump(mode="json"),
        "program": program.model_dump(mode="json"),
    }


def _create_project(client: TestClient, payload: dict) -> str:
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _wait_for_job(client: TestClient, job_id: str, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"finished", "failed"}:
            return payload
        time.sleep(0.1)
    raise AssertionError(f"El job {job_id} no terminó dentro del timeout")


def test_projects_crud_flow(client: TestClient, sample_solar_rectangular, sample_typology_t2: Typology) -> None:
    payload = _project_payload(sample_solar_rectangular, sample_typology_t2)
    project_id = _create_project(client, payload)

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    listed_project = next(project for project in list_response.json() if project["id"] == project_id)
    assert listed_project["status"] == "draft"

    detail_response = client.get(f"/api/projects/{project_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["current_version"]["version_number"] == 1
    assert detail_response.json()["status"] == "draft"

    updated_payload = _project_payload(sample_solar_rectangular, sample_typology_t2)
    updated_payload["name"] = "Wohnprojekt Aktualisiert"
    updated_payload["program"]["num_floors"] = 2
    update_response = client.put(f"/api/projects/{project_id}", json=updated_payload)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Wohnprojekt Aktualisiert"
    assert update_response.json()["current_version"]["version_number"] == 2

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/projects/{project_id}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    assert missing_response.json()["error"]["message"] == "Das Projekt wurde nicht gefunden."


def test_generation_job_websocket_and_downloads(
    client: TestClient,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project_id = _create_project(client, _project_payload(sample_solar_rectangular, sample_typology_t2))

    start_response = client.post(f"/api/projects/{project_id}/generate")
    assert start_response.status_code == 202
    job_id = start_response.json()["job_id"]

    events: list[str] = []
    with client.websocket_connect(f"/api/jobs/{job_id}/stream") as websocket:
        while True:
            event = websocket.receive_json()
            events.append(event.get("event", ""))
            if event.get("event") in {"finished", "failed"}:
                break

    job_payload = _wait_for_job(client, job_id)
    assert job_payload["status"] == "finished"
    assert "solver_started" in events
    assert "solver_finished" in events
    assert "builder_started" in events
    assert "export_started" in events
    assert "finished" in events

    for output_format in ("ifc", "dxf", "xlsx", "svg"):
        response = client.get(f"/api/projects/{project_id}/outputs/{output_format}")
        assert response.status_code == 200
        assert response.content


def test_health_endpoint_reports_dependencies(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["services"]["database"]["status"] == "ok"
    assert payload["services"]["ollama"]["status"] == "ok"
    assert payload["services"]["qdrant"]["status"] == "ok"