"""Tests del solver especializado de aparcamiento subterráneo."""

from collections import deque

import pytest

from cimiento.schemas import Point2D, Polygon2D, Program, Solar, Typology, TypologyMix
from cimiento.solver import solve, solve_parking

pytest_plugins = ["tests.fixtures.valid_cases"]


def _parking_space_bbox(space) -> tuple[float, float, float, float]:
    xs = [p.x for p in space.contour.points]
    ys = [p.y for p in space.contour.points]
    return min(xs), min(ys), max(xs), max(ys)


def test_solve_parking_generates_underground_storey(sample_typology_t2: Typology) -> None:
    solar = Solar(
        id="parking-solar-60x60",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=60.0, y=0.0),
                Point2D(x=60.0, y=60.0),
                Point2D(x=0.0, y=60.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=18.0,
    )
    program = Program(
        project_id="parking-project",
        num_floors=5,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=20)],
    )
    residential = solve(solar, program)

    parking = solve_parking(solar, residential, floor_height_m=program.floor_height_m)

    assert parking.status.name in {"OPTIMAL", "FEASIBLE"}
    assert parking.storey is not None
    assert parking.storey.level == -1
    assert parking.metrics.total_spaces == len(parking.storey.spaces)
    assert parking.storey.ramp_access.connected_lane_id
    assert parking.storey.lanes


def test_solve_parking_respects_accessible_ratio(sample_typology_t2: Typology) -> None:
    solar = Solar(
        id="parking-solar-50x50",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=50.0, y=0.0),
                Point2D(x=50.0, y=50.0),
                Point2D(x=0.0, y=50.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=15.0,
    )
    program = Program(
        project_id="parking-accessible",
        num_floors=4,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=16)],
    )
    residential = solve(solar, program)
    ratio = 0.10

    parking = solve_parking(
        solar,
        residential,
        floor_height_m=program.floor_height_m,
        accessible_ratio=ratio,
    )

    assert parking.storey is not None
    total = len(parking.storey.spaces)
    accessible = sum(1 for s in parking.storey.spaces if s.type.value == "ACCESSIBLE")
    assert total > 0
    assert accessible / total >= ratio - 1e-6


def test_all_parking_spaces_are_connected_to_ramp(sample_typology_t2: Typology) -> None:
    solar = Solar(
        id="parking-solar-55x55",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=55.0, y=0.0),
                Point2D(x=55.0, y=55.0),
                Point2D(x=0.0, y=55.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=18.0,
    )
    program = Program(
        project_id="parking-connectivity",
        num_floors=3,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=12)],
    )
    residential = solve(solar, program)
    parking = solve_parking(solar, residential, floor_height_m=program.floor_height_m)
    assert parking.storey is not None

    graph = {lane.id: set(lane.connected_lane_ids) for lane in parking.storey.lanes}
    for lane in parking.storey.lanes:
        for linked in lane.connected_lane_ids:
            graph.setdefault(linked, set()).add(lane.id)

    root = parking.storey.ramp_access.connected_lane_id
    seen = {root}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for neighbour in graph.get(current, set()):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)

    for space in parking.storey.spaces:
        assert space.lane_id in seen

    core_rects = [
        (core.position.x, core.position.y, core.position.x + core.width_m, core.position.y + core.depth_m)
        for core in residential.communication_cores
    ]
    for space in parking.storey.spaces:
        sx1, sy1, sx2, sy2 = _parking_space_bbox(space)
        for cx1, cy1, cx2, cy2 in core_rects:
            assert sx2 <= cx1 or cx2 <= sx1 or sy2 <= cy1 or cy2 <= sy1