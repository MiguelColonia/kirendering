"""Endpoint de salud de la aplicación y de sus dependencias."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import text

from cimiento.api.schemas import HealthResponse, ServiceHealthResponse
from cimiento.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

HealthCheck = Callable[[Request], Awaitable[dict[str, Any]]]


async def _check_database(request: Request) -> dict[str, Any]:
    engine = request.app.state.engine
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("La comprobación de base de datos falló: %s", exc)
        return {"status": "error", "detail": str(exc), "code": "DATABASE_UNAVAILABLE"}


async def _check_ollama(_: Request) -> dict[str, Any]:
    url = settings.ollama_host.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("La comprobación de Ollama falló: %s", exc)
        return {"status": "error", "detail": str(exc), "code": "OLLAMA_UNAVAILABLE"}


async def _check_qdrant(_: Request) -> dict[str, Any]:
    url = f"http://{settings.qdrant_host}:{settings.qdrant_port}/collections"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("La comprobación de Qdrant falló: %s", exc)
        return {"status": "error", "detail": str(exc), "code": "QDRANT_UNAVAILABLE"}


async def _run_health_check(request: Request, name: str, default: HealthCheck) -> dict[str, Any]:
    overrides: dict[str, HealthCheck] = request.app.state.health_checks
    checker = overrides.get(name, default)
    return await checker(request)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    raw_services = {
        "database": await _run_health_check(request, "database", _check_database),
        "ollama": await _run_health_check(request, "ollama", _check_ollama),
        "qdrant": await _run_health_check(request, "qdrant", _check_qdrant),
    }
    services = {
        name: ServiceHealthResponse.model_validate(service) for name, service in raw_services.items()
    }
    overall_status = "ok" if all(service.status == "ok" for service in services.values()) else "degraded"
    return HealthResponse(status=overall_status, app=request.app.title, services=services)