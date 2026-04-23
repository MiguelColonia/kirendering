"""Repositorio async para CRUD de proyectos y sus versiones."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

from cimiento.core.config import settings
from cimiento.persistence.models import Base, GeneratedOutput, Project, ProjectVersion
from cimiento.schemas import Program, Solar, Solution


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uses_in_memory_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite+aiosqlite") and ":memory:" in database_url


def create_engine_from_url(database_url: str, *, echo: bool = False):
    """Crea un motor async compatible con PostgreSQL o SQLite."""
    kwargs: dict[str, Any] = {"echo": echo}
    if _uses_in_memory_sqlite(database_url):
        kwargs["poolclass"] = StaticPool
    return create_async_engine(database_url, **kwargs)


def create_async_session_factory(
    database_url: str | None = None,
    *,
    echo: bool = False,
) -> async_sessionmaker[AsyncSession]:
    """Devuelve una factoría de sesiones async para el repositorio."""
    engine = create_engine_from_url(database_url or settings.database_url, echo=echo)
    return async_sessionmaker(engine, expire_on_commit=False)


class ProjectRepository:
    """Acceso async a proyectos, versiones y outputs generados."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _touch_project(self, session: AsyncSession, project_id: str) -> None:
        project = await session.get(Project, project_id)
        if project is not None:
            project.updated_at = _utcnow()

    async def create_project(self, *, name: str, description: str | None = None) -> Project:
        async with self._session_factory() as session:
            project = Project(name=name, description=description)
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project

    async def get_project(self, project_id: str) -> Project | None:
        async with self._session_factory() as session:
            stmt = (
                select(Project)
                .options(selectinload(Project.versions))
                .where(Project.id == project_id)
            )
            return await session.scalar(stmt)

    async def list_projects(self) -> list[Project]:
        async with self._session_factory() as session:
            stmt = (
                select(Project).options(selectinload(Project.versions)).order_by(Project.created_at)
            )
            result = await session.scalars(stmt)
            return list(result.all())

    async def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project | None:
        async with self._session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                return None
            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            await session.commit()
            await session.refresh(project)
            return project

    async def delete_project(self, project_id: str) -> bool:
        async with self._session_factory() as session:
            project = await session.get(Project, project_id)
            if project is None:
                return False
            await session.delete(project)
            await session.commit()
            return True

    async def create_project_version(
        self,
        project_id: str,
        *,
        solar: Solar,
        program: Program,
        solution: Solution | None = None,
    ) -> ProjectVersion:
        # Concurrent version creation can observe the same MAX(version_number).
        # Retry after unique-constraint collisions so numbering remains monotonic.
        for _ in range(5):
            async with self._session_factory() as session:
                project = await session.get(Project, project_id)
                if project is None:
                    raise ValueError(f"Proyecto no encontrado: {project_id}")

                current_max = await session.scalar(
                    select(func.max(ProjectVersion.version_number)).where(
                        ProjectVersion.project_id == project_id
                    )
                )
                next_version = (current_max or 0) + 1

                version = ProjectVersion(
                    project_id=project_id,
                    version_number=next_version,
                    solar_data=solar.model_dump(mode="json"),
                    program_data=program.model_dump(mode="json"),
                    solution_data=solution.model_dump(mode="json") if solution is not None else None,
                )
                session.add(version)
                await self._touch_project(session, project_id)
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    continue

                await session.refresh(version)
                return version

        raise RuntimeError(
            f"No se pudo crear una nueva versión concurrente para el proyecto {project_id}"
        )

    async def get_project_version(self, version_id: str) -> ProjectVersion | None:
        async with self._session_factory() as session:
            stmt = (
                select(ProjectVersion)
                .options(selectinload(ProjectVersion.generated_outputs))
                .where(ProjectVersion.id == version_id)
            )
            return await session.scalar(stmt)

    async def list_project_versions(self, project_id: str) -> list[ProjectVersion]:
        async with self._session_factory() as session:
            stmt = (
                select(ProjectVersion)
                .options(selectinload(ProjectVersion.generated_outputs))
                .where(ProjectVersion.project_id == project_id)
                .order_by(ProjectVersion.version_number)
            )
            result = await session.scalars(stmt)
            return list(result.all())

    async def get_latest_project_version(self, project_id: str) -> ProjectVersion | None:
        async with self._session_factory() as session:
            stmt = (
                select(ProjectVersion)
                .options(selectinload(ProjectVersion.generated_outputs))
                .where(ProjectVersion.project_id == project_id)
                .order_by(ProjectVersion.version_number.desc())
                .limit(1)
            )
            return await session.scalar(stmt)

    async def update_project_version(
        self,
        version_id: str,
        *,
        solar: Solar | None = None,
        program: Program | None = None,
        solution: Solution | None = None,
    ) -> ProjectVersion | None:
        async with self._session_factory() as session:
            version = await session.get(ProjectVersion, version_id)
            if version is None:
                return None
            if solar is not None:
                version.solar_data = solar.model_dump(mode="json")
            if program is not None:
                version.program_data = program.model_dump(mode="json")
            if solution is not None:
                version.solution_data = solution.model_dump(mode="json")
            await self._touch_project(session, version.project_id)
            await session.commit()
            await session.refresh(version)
            return version

    async def delete_project_version(self, version_id: str) -> bool:
        async with self._session_factory() as session:
            version = await session.get(ProjectVersion, version_id)
            if version is None:
                return False
            await self._touch_project(session, version.project_id)
            await session.delete(version)
            await session.commit()
            return True

    async def create_generated_output(
        self,
        project_version_id: str,
        *,
        output_type: str,
        file_path: str,
        media_type: str | None = None,
        output_metadata: dict[str, Any] | None = None,
    ) -> GeneratedOutput:
        async with self._session_factory() as session:
            version = await session.get(ProjectVersion, project_version_id)
            if version is None:
                raise ValueError(f"Versión no encontrada: {project_version_id}")

            output = GeneratedOutput(
                project_version_id=project_version_id,
                output_type=output_type,
                file_path=file_path,
                media_type=media_type,
                output_metadata=output_metadata or {},
            )
            session.add(output)
            await self._touch_project(session, version.project_id)
            await session.commit()
            await session.refresh(output)
            return output

    async def get_generated_output(self, output_id: str) -> GeneratedOutput | None:
        async with self._session_factory() as session:
            return await session.get(GeneratedOutput, output_id)

    async def list_generated_outputs(self, project_version_id: str) -> list[GeneratedOutput]:
        async with self._session_factory() as session:
            stmt = (
                select(GeneratedOutput)
                .where(GeneratedOutput.project_version_id == project_version_id)
                .order_by(GeneratedOutput.created_at)
            )
            result = await session.scalars(stmt)
            return list(result.all())

    async def get_latest_generated_output(
        self,
        project_version_id: str,
        output_type: str,
    ) -> GeneratedOutput | None:
        async with self._session_factory() as session:
            stmt = (
                select(GeneratedOutput)
                .where(
                    GeneratedOutput.project_version_id == project_version_id,
                    GeneratedOutput.output_type == output_type,
                )
                .order_by(GeneratedOutput.created_at.desc())
                .limit(1)
            )
            return await session.scalar(stmt)

    async def update_generated_output(
        self,
        output_id: str,
        *,
        file_path: str | None = None,
        media_type: str | None = None,
        output_metadata: dict[str, Any] | None = None,
    ) -> GeneratedOutput | None:
        async with self._session_factory() as session:
            output = await session.get(GeneratedOutput, output_id)
            if output is None:
                return None
            if file_path is not None:
                output.file_path = file_path
            if media_type is not None:
                output.media_type = media_type
            if output_metadata is not None:
                output.output_metadata = output_metadata
            version = await session.get(ProjectVersion, output.project_version_id)
            if version is not None:
                await self._touch_project(session, version.project_id)
            await session.commit()
            await session.refresh(output)
            return output

    async def delete_generated_output(self, output_id: str) -> bool:
        async with self._session_factory() as session:
            output = await session.get(GeneratedOutput, output_id)
            if output is None:
                return False
            version = await session.get(ProjectVersion, output.project_version_id)
            if version is not None:
                await self._touch_project(session, version.project_id)
            await session.delete(output)
            await session.commit()
            return True

    async def create_schema(self) -> None:
        """Crea todas las tablas de persistencia en la base configurada."""
        engine = self._session_factory.kw["bind"]
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
