"""Modelos SQLAlchemy async para la persistencia de proyectos."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarativa compartida por todos los modelos de persistencia."""


class TimestampMixin:
    """Campos comunes de auditoría temporal."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )


class Project(TimestampMixin, Base):
    """Proyecto persistido y listo para versionado."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    versions: Mapped[list[ProjectVersion]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVersion.version_number",
    )


class ProjectVersion(TimestampMixin, Base):
    """Versión inmutable de un proyecto con snapshots serializados en JSON."""

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    solar_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    program_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    solution_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    project: Mapped[Project] = relationship(back_populates="versions")
    generated_outputs: Mapped[list[GeneratedOutput]] = relationship(
        back_populates="project_version",
        cascade="all, delete-orphan",
    )

    def get_solar_model(self):
        """Reconstruye el schema Solar desde el snapshot JSON."""
        from cimiento.schemas import Solar

        return Solar.model_validate(self.solar_data)

    def get_program_model(self):
        """Reconstruye el schema Program desde el snapshot JSON."""
        from cimiento.schemas import Program

        return Program.model_validate(self.program_data)

    def get_solution_model(self):
        """Reconstruye el schema Solution si existe un snapshot asociado."""
        from cimiento.schemas import Solution

        if self.solution_data is None:
            return None
        return Solution.model_validate(self.solution_data)


class GeneratedOutput(TimestampMixin, Base):
    """Output derivado generado para una versión concreta del proyecto."""

    __tablename__ = "generated_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    output_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    project_version: Mapped[ProjectVersion] = relationship(back_populates="generated_outputs")