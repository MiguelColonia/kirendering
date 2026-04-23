"""Tests async del repositorio de proyectos usando SQLite en memoria."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from cimiento.persistence.models import Base
from cimiento.persistence.repository import ProjectRepository, create_engine_from_url
from cimiento.schemas import (
    CommunicationCore,
    Point2D,
    Program,
    Solution,
    SolutionMetrics,
    SolutionStatus,
    Typology,
    TypologyMix,
    UnitPlacement,
)
from cimiento.schemas.geometry_primitives import Rectangle

pytest_plugins = ["tests.fixtures.valid_cases"]


@pytest.fixture
async def repository() -> ProjectRepository:
    engine = create_engine_from_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = ProjectRepository(session_factory)
    try:
        yield repo
    finally:
        await engine.dispose()


def _sample_solution() -> Solution:
    return Solution(
        status=SolutionStatus.FEASIBLE,
        placements=[
            UnitPlacement(
                typology_id="T2",
                floor=0,
                bbox=Rectangle(x=0.0, y=0.0, width=7.0, height=10.0),
            )
        ],
        communication_cores=[
            CommunicationCore(
                position=Point2D(x=12.0, y=8.0),
                width_m=4.0,
                depth_m=6.0,
                has_elevator=True,
                serves_floors=[0, 1],
            )
        ],
        metrics=SolutionMetrics(
            total_assigned_area=70.0,
            num_units_placed=1,
            typology_fulfillment={"T2": 1.0},
        ),
        solver_time_seconds=0.1,
    )


def _sample_program(sample_typology_t2: Typology) -> Program:
    return Program(
        project_id="repo-project",
        num_floors=2,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=1)],
    )


@pytest.mark.asyncio
async def test_create_project_and_version_roundtrip(
    repository: ProjectRepository,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project = await repository.create_project(name="Proyecto repositorio", description="demo")
    version = await repository.create_project_version(
        project.id,
        solar=sample_solar_rectangular,
        program=_sample_program(sample_typology_t2),
        solution=_sample_solution(),
    )

    fetched_project = await repository.get_project(project.id)
    fetched_version = await repository.get_project_version(version.id)

    assert fetched_project is not None
    assert fetched_project.name == "Proyecto repositorio"
    assert fetched_version is not None
    assert fetched_version.version_number == 1
    assert fetched_version.get_solar_model().id == sample_solar_rectangular.id
    assert fetched_version.get_program_model().project_id == "repo-project"
    assert fetched_version.get_solution_model().metrics.num_units_placed == 1


@pytest.mark.asyncio
async def test_versions_increment_and_can_be_updated(
    repository: ProjectRepository,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project = await repository.create_project(name="Proyecto v2")
    program = _sample_program(sample_typology_t2)

    first = await repository.create_project_version(
        project.id, solar=sample_solar_rectangular, program=program
    )
    second = await repository.create_project_version(
        project.id, solar=sample_solar_rectangular, program=program
    )

    updated_project = await repository.update_project(project.id, name="Proyecto v2 actualizado")
    updated_second = await repository.update_project_version(second.id, solution=_sample_solution())

    assert first.version_number == 1
    assert second.version_number == 2
    assert updated_project is not None
    assert updated_project.name == "Proyecto v2 actualizado"
    assert updated_second is not None
    assert updated_second.get_solution_model() is not None


@pytest.mark.asyncio
async def test_generated_output_crud_and_project_delete_cascade(
    repository: ProjectRepository,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project = await repository.create_project(name="Proyecto outputs")
    version = await repository.create_project_version(
        project.id,
        solar=sample_solar_rectangular,
        program=_sample_program(sample_typology_t2),
    )

    output = await repository.create_generated_output(
        version.id,
        output_type="IFC",
        file_path="data/outputs/demo.ifc",
        media_type="application/x-step",
        output_metadata={"size_bytes": 1024},
    )
    listed = await repository.list_generated_outputs(version.id)
    updated = await repository.update_generated_output(
        output.id,
        file_path="data/outputs/demo-v2.ifc",
        output_metadata={"size_bytes": 2048},
    )

    assert len(listed) == 1
    assert updated is not None
    assert updated.file_path.endswith("demo-v2.ifc")
    assert updated.output_metadata["size_bytes"] == 2048

    deleted = await repository.delete_project(project.id)
    assert deleted is True
    assert await repository.get_project(project.id) is None
    assert await repository.get_project_version(version.id) is None
    assert await repository.get_generated_output(output.id) is None


@pytest.mark.asyncio
async def test_project_updated_at_changes_when_creating_new_version(
    repository: ProjectRepository,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project = await repository.create_project(name="Proyecto timestamp")
    created_at = project.updated_at

    await repository.create_project_version(
        project.id,
        solar=sample_solar_rectangular,
        program=_sample_program(sample_typology_t2),
    )

    refreshed_project = await repository.get_project(project.id)

    assert refreshed_project is not None
    assert refreshed_project.updated_at > created_at


@pytest.mark.asyncio
async def test_project_updated_at_changes_when_version_or_outputs_change(
    repository: ProjectRepository,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    project = await repository.create_project(name="Proyecto timestamp outputs")
    version = await repository.create_project_version(
        project.id,
        solar=sample_solar_rectangular,
        program=_sample_program(sample_typology_t2),
    )
    after_version = (await repository.get_project(project.id)).updated_at

    updated_version = await repository.update_project_version(
        version.id,
        solution=_sample_solution(),
    )
    assert updated_version is not None

    after_solution = (await repository.get_project(project.id)).updated_at
    assert after_solution > after_version

    await repository.create_generated_output(
        version.id,
        output_type="IFC",
        file_path="data/outputs/timestamp.ifc",
        media_type="application/x-step",
    )

    after_output = (await repository.get_project(project.id)).updated_at
    assert after_output > after_solution


@pytest.mark.asyncio
async def test_concurrent_version_creation_assigns_unique_numbers(
    tmp_path,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> None:
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{tmp_path / 'concurrent-versions.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = ProjectRepository(session_factory)

    try:
        project = await repository.create_project(name="Proyecto concurrente")
        program = _sample_program(sample_typology_t2).model_copy(
            update={"project_id": project.id}
        )

        first, second = await asyncio.gather(
            repository.create_project_version(
                project.id,
                solar=sample_solar_rectangular,
                program=program,
            ),
            repository.create_project_version(
                project.id,
                solar=sample_solar_rectangular,
                program=program,
            ),
        )

        assert sorted([first.version_number, second.version_number]) == [1, 2]

        versions = await repository.list_project_versions(project.id)
        assert [version.version_number for version in versions] == [1, 2]
    finally:
        await engine.dispose()
