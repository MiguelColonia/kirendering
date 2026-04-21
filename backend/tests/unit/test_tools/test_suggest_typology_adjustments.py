"""Tests del tool suggest_typology_adjustments."""

import pytest

from cimiento.llm.tools.suggest_typology_adjustments import (
    AdjustmentResult,
    suggest_typology_adjustments,
)
from cimiento.schemas import Point2D, Polygon2D, Program, Room, RoomType, Solar, Typology, TypologyMix
from cimiento.schemas.solution import Solution, SolutionMetrics, SolutionStatus


def _make_program(count: int = 5, num_floors: int = 1) -> Program:
    typology = Typology(
        id="T2", name="T2", min_useful_area=70.0, max_useful_area=90.0,
        num_bedrooms=2, num_bathrooms=1,
        rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5)],
    )
    return Program(
        project_id="p1", num_floors=num_floors, floor_height_m=3.0,
        typologies=[typology],
        mix=[TypologyMix(typology_id="T2", count=count)],
    )


def _make_solution(status: SolutionStatus, placed: int = 0) -> Solution:
    return Solution(
        status=status,
        placements=[],
        communication_cores=[],
        metrics=SolutionMetrics(
            total_assigned_area=0.0,
            num_units_placed=placed,
            typology_fulfillment={"T2": placed / 5 if placed else 0.0},
        ),
        solver_time_seconds=1.0,
        message="Test message" if status == SolutionStatus.INFEASIBLE else None,
    )


def test_suggest_infeasible_returns_suggestions() -> None:
    program = _make_program(count=5)
    solution = _make_solution(SolutionStatus.INFEASIBLE)
    result = suggest_typology_adjustments(program, solution)
    assert isinstance(result, AdjustmentResult)
    assert result.original_status == SolutionStatus.INFEASIBLE
    assert len(result.suggestions) > 0


def test_suggest_infeasible_reduces_mix() -> None:
    program = _make_program(count=10)
    solution = _make_solution(SolutionStatus.INFEASIBLE)
    result = suggest_typology_adjustments(program, solution)
    for suggestion in result.suggestions:
        new_total = sum(e.count for e in suggestion.adjusted_program.mix)
        original_total = sum(e.count for e in program.mix)
        assert new_total <= original_total


def test_suggest_optimal_returns_no_suggestions() -> None:
    program = _make_program(count=3)
    solution = _make_solution(SolutionStatus.OPTIMAL, placed=3)
    result = suggest_typology_adjustments(program, solution)
    assert result.original_status == SolutionStatus.OPTIMAL
    assert len(result.suggestions) == 0


def test_suggest_max_suggestions_respected() -> None:
    program = _make_program(count=10)
    solution = _make_solution(SolutionStatus.INFEASIBLE)
    result = suggest_typology_adjustments(program, solution, max_suggestions=2)
    assert len(result.suggestions) <= 2


def test_suggest_adjusted_programs_are_valid() -> None:
    """Los programas ajustados son Pydantic válidos y listos para solve_layout."""
    program = _make_program(count=8)
    solution = _make_solution(SolutionStatus.INFEASIBLE)
    result = suggest_typology_adjustments(program, solution)
    for suggestion in result.suggestions:
        assert suggestion.adjusted_program.project_id == program.project_id
        for entry in suggestion.adjusted_program.mix:
            assert entry.count >= 1


def test_suggest_timeout_proposes_floor_addition() -> None:
    program = _make_program(count=5)
    solution = _make_solution(SolutionStatus.TIMEOUT, placed=3)
    result = suggest_typology_adjustments(program, solution)
    floor_suggestions = [
        s for s in result.suggestions
        if s.adjusted_program.num_floors > program.num_floors
    ]
    assert len(floor_suggestions) > 0


def test_suggest_explanation_non_empty() -> None:
    program = _make_program(count=5)
    solution = _make_solution(SolutionStatus.INFEASIBLE)
    result = suggest_typology_adjustments(program, solution)
    assert len(result.explanation) > 10
