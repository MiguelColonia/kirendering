"""Errores estándar y respuestas HTTP localizadas para la API."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def api_error(status_code: int, code: str, **context: Any) -> HTTPException:
    """Construye una HTTPException con código estándar y metadatos opcionales."""
    return HTTPException(status_code=status_code, detail={"code": code, "context": context})


def project_not_found(project_id: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", project_id=project_id)


def job_not_found(job_id: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", job_id=job_id)


def output_not_found(project_id: str, output_format: str) -> HTTPException:
    return api_error(
        status.HTTP_404_NOT_FOUND,
        "OUTPUT_NOT_FOUND",
        project_id=project_id,
        output_format=output_format,
    )


def render_not_found(render_id: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "RENDER_NOT_FOUND", render_id=render_id)


def diffusion_not_found(diffusion_id: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "DIFFUSION_NOT_FOUND", diffusion_id=diffusion_id)
