"""Dependencias compartidas de la capa API."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from cimiento.api.jobs import JobManager
from cimiento.persistence.repository import ProjectRepository


def get_repository(request: Request) -> ProjectRepository:
    """Devuelve un repositorio enlazado a la sesión async de la aplicación."""
    return ProjectRepository(request.app.state.session_factory)


def get_job_manager(request: Request) -> JobManager:
    """Devuelve el gestor en memoria de trabajos de generación."""
    return request.app.state.job_manager


def get_output_root(request: Request) -> Path:
    """Devuelve la carpeta base de outputs de la aplicación."""
    return request.app.state.output_root
