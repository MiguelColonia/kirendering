"""Gestor en memoria de trabajos de generación y streaming de eventos."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GenerationJob:
    """Estado observable de un trabajo de generación."""

    id: str
    project_id: str
    version_id: str
    status: str = "queued"
    events: list[dict[str, Any]] = field(default_factory=list)
    output_formats: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    task: asyncio.Task[Any] | None = None


class JobManager:
    """Registro en memoria de jobs y colas de suscriptores WebSocket."""

    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._listeners: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def create_job(self, project_id: str, version_id: str) -> GenerationJob:
        job = GenerationJob(id=str(uuid4()), project_id=project_id, version_id=version_id)
        self._jobs[job.id] = job
        self._listeners[job.id] = set()
        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self._jobs.get(job_id)

    def set_task(self, job_id: str, task: asyncio.Task[Any]) -> None:
        job = self._jobs[job_id]
        job.task = task

    async def publish(
        self,
        job_id: str,
        event: str,
        *,
        data: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        job = self._jobs[job_id]
        if status is not None:
            job.status = status
        payload = {
            "event": event,
            "job_id": job_id,
            "timestamp": _utcnow_iso(),
            "data": data or {},
        }
        job.events.append(payload)
        for queue in list(self._listeners.get(job_id, set())):
            await queue.put(payload)

    async def fail(self, job_id: str, *, code: str, message: str) -> None:
        job = self._jobs[job_id]
        job.status = "failed"
        job.error_code = code
        job.error_message = message
        await self.publish(job_id, "failed", data={"code": code, "message": message})

    async def finish(self, job_id: str, *, output_formats: list[str]) -> None:
        job = self._jobs[job_id]
        job.status = "finished"
        job.output_formats = output_formats
        await self.publish(job_id, "finished", data={"output_formats": output_formats})

    def subscribe(self, job_id: str) -> tuple[list[dict[str, Any]], asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._listeners.setdefault(job_id, set()).add(queue)
        backlog = list(self._jobs[job_id].events)
        return backlog, queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        listeners = self._listeners.get(job_id)
        if listeners is not None:
            listeners.discard(queue)