"""Tests del tool solve_layout."""

import pytest

from cimiento.llm.tools.solve_layout import SolveLayoutInput, SolveLayoutOutput, solve_layout
from cimiento.schemas import (
    Point2D,
    Polygon2D,
    Program,
    Room,
    RoomType,
    Solar,
    Typology,
    TypologyMix,
)
from cimiento.schemas.solution import SolutionStatus


@pytest.fixture
def solar_20x30() -> Solar:
    return Solar(
        id="s1",
        contour=Polygon2D(points=[
            Point2D(x=0, y=0), Point2D(x=20, y=0),
            Point2D(x=20, y=30), Point2D(x=0, y=30),
        ]),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )


@pytest.fixture
def typology_t2() -> Typology:
    return Typology(
        id="T2", name="T2", min_useful_area=70.0, max_useful_area=90.0,
        num_bedrooms=2, num_bathrooms=1,
        rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5)],
    )


def test_solve_layout_returns_output(solar_20x30: Solar, typology_t2: Typology) -> None:
    input_ = SolveLayoutInput(
        solar=solar_20x30,
        program=Program(
            project_id="p1", num_floors=1, floor_height_m=3.0,
            typologies=[typology_t2],
            mix=[TypologyMix(typology_id="T2", count=2)],
        ),
    )
    result = solve_layout(input_)
    assert isinstance(result, SolveLayoutOutput)


def test_solve_layout_feasible(solar_20x30: Solar, typology_t2: Typology) -> None:
    input_ = SolveLayoutInput(
        solar=solar_20x30,
        program=Program(
            project_id="p1", num_floors=1, floor_height_m=3.0,
            typologies=[typology_t2],
            mix=[TypologyMix(typology_id="T2", count=2)],
        ),
        timeout_seconds=30,
    )
    result = solve_layout(input_)
    assert result.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert result.num_units_placed == 2


def test_solve_layout_solution_embedded(solar_20x30: Solar, typology_t2: Typology) -> None:
    """La Solution embebida es consistente con las métricas del output."""
    input_ = SolveLayoutInput(
        solar=solar_20x30,
        program=Program(
            project_id="p1", num_floors=1, floor_height_m=3.0,
            typologies=[typology_t2],
            mix=[TypologyMix(typology_id="T2", count=2)],
        ),
        timeout_seconds=30,
    )
    result = solve_layout(input_)
    assert result.num_units_placed == result.solution.metrics.num_units_placed
    assert result.total_area_m2 == result.solution.metrics.total_assigned_area


def test_solve_layout_infeasible_tiny_solar(typology_t2: Typology) -> None:
    tiny = Solar(
        id="tiny",
        contour=Polygon2D(points=[
            Point2D(x=0, y=0), Point2D(x=5, y=0),
            Point2D(x=5, y=5), Point2D(x=0, y=5),
        ]),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )
    input_ = SolveLayoutInput(
        solar=tiny,
        program=Program(
            project_id="p2", num_floors=1, floor_height_m=3.0,
            typologies=[typology_t2],
            mix=[TypologyMix(typology_id="T2", count=1)],
        ),
        timeout_seconds=5,
    )
    result = solve_layout(input_)
    assert result.status == SolutionStatus.INFEASIBLE
