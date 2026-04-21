"""Entrypoint FastAPI de la Fase 4."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import MemorySaver
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from cimiento.api.i18n import translate_error
from cimiento.api.jobs import JobManager
from cimiento.api.routers.chat import router as chat_router
from cimiento.api.routers.downloads import router as downloads_router
from cimiento.api.routers.generation import router as generation_router
from cimiento.api.routers.health import router as health_router
from cimiento.api.routers.projects import router as projects_router
from cimiento.core.config import settings
from cimiento.llm.client import OllamaClient
from cimiento.llm.graphs import build_graph
from cimiento.persistence.models import Base
from cimiento.persistence.repository import create_engine_from_url

logger = logging.getLogger(__name__)

HealthCheck = Callable[[Request], Awaitable[dict[str, Any]]]


def create_app(
    *,
    database_url: str | None = None,
    output_root: Path | None = None,
    health_checks: dict[str, HealthCheck] | None = None,
) -> FastAPI:
    db_url = database_url or settings.database_url
    resolved_output_root = output_root or (
        Path(__file__).resolve().parents[3] / "data" / "outputs" / "api"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Inicializando aplicación FastAPI")
        engine = create_engine_from_url(db_url, echo=settings.debug)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.job_manager = JobManager()
        app.state.output_root = resolved_output_root
        app.state.settings = settings
        app.state.health_checks = health_checks or {}
        resolved_output_root.mkdir(parents=True, exist_ok=True)

        if db_url.startswith("sqlite+aiosqlite"):
            logger.info("Creando schema SQLite de desarrollo si no existe")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        chat_client = OllamaClient(settings=settings)
        app.state.chat_client = chat_client

        qdrant = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        app.state.qdrant_client = qdrant

        app.state.chat_graph = build_graph(
            client=chat_client,
            checkpointer=MemorySaver(),
            qdrant_client=qdrant,
        )
        logger.info("Grafo de chat y cliente Qdrant inicializados")

        try:
            yield
        finally:
            logger.info("Cerrando recursos de la aplicación FastAPI")
            await app.state.chat_client.aclose()
            await app.state.qdrant_client.close()
            await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        openapi_url="/api/schemas/openapi.json",
    )

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_compat() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.middleware("http")
    async def localized_errors_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.detail)}
            code = detail.get("code", "INTERNAL_ERROR")
            context = detail.get("context", {})
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": code, "message": translate_error(code, **context)}},
            )
        except Exception:  # noqa: BLE001
            logger.exception("Error interno no controlado en la API")
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": translate_error("INTERNAL_ERROR"),
                    }
                },
            )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, __: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": translate_error("VALIDATION_ERROR"),
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            code = exc.detail.get("code", "INTERNAL_ERROR")
            context = exc.detail.get("context", {})
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": code, "message": translate_error(code, **context)}},
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(projects_router)
    app.include_router(generation_router)
    app.include_router(downloads_router)
    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()
# La función create_app se encarga de inicializar y configurar la aplicación FastAPI,
# incluyendo la configuración de middlewares, routers, y recursos compartidos como
# clientes de chat y bases de datos. Esta función devuelve una instancia de FastAPI
# lista para ser utilizada.
