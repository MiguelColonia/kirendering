"""Tests del tool calculate_metrics."""

import pytest

from cimiento.geometry.builder import build_building_from_solution
from cimiento.llm.tools.calculate_metrics import UrbanMetrics, calculate_metrics
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
from cimiento.solver.engine import solve


@pytest.fixture
def solar_20x30() -> Solar:
    return Solar(
        id="s1",
        contour=Polygon2D(
            points=[
                Point2D(x=0, y=0),
                Point2D(x=20, y=0),
                Point2D(x=20, y=30),
                Point2D(x=0, y=30),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )


@pytest.fixture
def program_2_t2(solar_20x30: Solar) -> Program:
    typology = Typology(
        id="T2",
        name="T2",
        min_useful_area=70.0,
        max_useful_area=90.0,
        num_bedrooms=2,
        num_bathrooms=1,
        rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5)],
    )
    return Program(
        project_id="p1",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[typology],
        mix=[TypologyMix(typology_id="T2", count=2)],
    )


def test_calculate_metrics_returns_urban_metrics(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert isinstance(metrics, UrbanMetrics)


def test_calculate_metrics_solar_area(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert metrics.solar_area_m2 == pytest.approx(600.0, abs=0.5)


def test_calculate_metrics_num_units(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert metrics.num_units == solution.metrics.num_units_placed


def test_calculate_metrics_far_positive(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert metrics.floor_area_ratio > 0.0
    assert metrics.floor_area_ratio < 10.0


def test_calculate_metrics_coverage_bounded(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert 0.0 <= metrics.site_coverage_ratio <= 1.0


def test_calculate_metrics_density_positive(solar_20x30: Solar, program_2_t2: Program) -> None:
    solution = solve(solar_20x30, program_2_t2, timeout_seconds=30)
    building = build_building_from_solution(solar_20x30, program_2_t2, solution)
    metrics = calculate_metrics(building, solar_20x30)
    assert metrics.density_units_per_ha > 0.0
