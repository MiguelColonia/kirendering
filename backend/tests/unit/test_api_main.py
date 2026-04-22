"""Tests unitarios básicos para el endpoint de salud de la API y el registro de routers."""

from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from cimiento.api.main import create_app


async def _ok(_: object) -> dict[str, str]:
    return {"status": "ok"}


def _build_client() -> TestClient:
    app = create_app(
        database_url="sqlite+aiosqlite:///:memory:",
        health_checks={"ollama": _ok, "qdrant": _ok},
    )
    return TestClient(app)


def test_health_happy_path_returns_ok_and_app_name() -> None:
    # Given: un cliente HTTP contra la app FastAPI en estado normal
    with _build_client() as client:
        # When: se consulta el endpoint de salud
        response = client.get("/health")

        # Then: responde 200 con payload esperado
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] in {"ok", "degraded"}
        assert payload["app"] == "Cimiento"
        assert "database" in payload["services"]
        assert "ollama" in payload["services"]
        assert "qdrant" in payload["services"]


def test_health_method_not_allowed_for_post() -> None:
    # Given: un cliente HTTP estándar
    with _build_client() as client:
        # When: se envía POST a una ruta definida solo para GET
        response = client.post("/health")

        # Then: se devuelve 405 Method Not Allowed
        assert response.status_code == 405


def test_health_unknown_route_returns_404() -> None:
    # Given: un cliente HTTP estándar
    with _build_client() as client:
        # When: se consulta una ruta inexistente
        response = client.get("/route-does-not-exist")

        # Then: se devuelve 404 Not Found
        assert response.status_code == 404


def test_openapi_schema_is_available_on_new_and_legacy_routes() -> None:
    # Given: un cliente HTTP estándar
    with _build_client() as client:
        # When: se consulta el schema OpenAPI en la nueva ruta y en la ruta legacy
        routed_response = client.get("/api/schemas/openapi.json")
        legacy_response = client.get("/openapi.json")

        # Then: ambas devuelven el mismo documento OpenAPI
        assert routed_response.status_code == 200
        assert legacy_response.status_code == 200
        routed_payload = routed_response.json()
        assert routed_payload["info"]["title"] == "Cimiento"
        assert "/health" in routed_payload["paths"]
        assert legacy_response.json() == routed_payload


def test_vision_analyze_endpoint_is_registered_in_openapi() -> None:
    # Given: la app FastAPI inicializada
    with _build_client() as client:
        schema = client.get("/api/schemas/openapi.json").json()
        paths = schema["paths"]

        # Then: el endpoint de análisis visual está registrado
        vision_path = "/api/projects/{project_id}/vision/analyze"
        assert vision_path in paths, f"Ruta {vision_path} no encontrada en OpenAPI"
        assert "post" in paths[vision_path]


def test_patch_program_endpoint_is_registered_in_openapi() -> None:
    # Given: la app FastAPI inicializada
    with _build_client() as client:
        schema = client.get("/api/schemas/openapi.json").json()
        paths = schema["paths"]

        # Then: los endpoints PATCH de programa y solar están registrados
        program_path = "/api/projects/{project_id}/program"
        solar_path = "/api/projects/{project_id}/solar"
        assert program_path in paths, f"Ruta {program_path} no encontrada en OpenAPI"
        assert "patch" in paths[program_path]
        assert solar_path in paths, f"Ruta {solar_path} no encontrada en OpenAPI"
        assert "patch" in paths[solar_path]


def test_pyproject_includes_python_multipart_dependency() -> None:
    # Given: el pyproject.toml del proyecto backend
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml no encontrado"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    # Then: python-multipart está declarado como dependencia (necesario para UploadFile)
    deps: list[str] = data["project"]["dependencies"]
    assert any("python-multipart" in dep for dep in deps), (
        "python-multipart no está en las dependencias de pyproject.toml. "
        "Es requerido por FastAPI para manejar UploadFile en el router de visión."
    )


def test_python_multipart_is_importable() -> None:
    # Given / When: se intenta importar python-multipart en el entorno actual
    try:
        import multipart  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "python-multipart no está instalado en el entorno. "
            "Ejecuta: uv pip install python-multipart"
        ) from exc
