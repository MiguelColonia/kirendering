"""Solver especializado para planta de aparcamiento subterráneo.

La estrategia es secuencial respecto al solver residencial:

1. Se toma el bbox del solar y los núcleos verticales ya fijados.
2. Se ensayan varias plantillas conectadas a una rampa de acceso.
3. Para cada plantilla, un modelo CP-SAT maximiza plazas de coche por bandas útiles
   respetando el ratio mínimo de plazas accesibles.
4. Las plazas de motocicleta se asignan después, solo sobre longitudes residuales.

El resultado no pretende resolver toda la casuística normativa de un aparcamiento real,
pero sí establecer una base reproducible, conectada y exportable a BIM.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from cimiento.schemas.architectural import (
    CommunicationCore,
    ParkingDimensions,
    ParkingLane,
    ParkingSpace,
    ParkingSpaceType,
    ParkingStorey,
    RampAccess,
)
from cimiento.schemas.geometry_primitives import Point2D, Polygon2D, Rectangle
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import (
    ParkingSolution,
    ParkingSolutionMetrics,
    Solution,
    SolutionStatus,
)

_STANDARD_WIDTH_M = 2.5
_STANDARD_DEPTH_M = 5.0
_ACCESSIBLE_WIDTH_M = 3.6
_ACCESSIBLE_DEPTH_M = 5.0
_MOTORCYCLE_WIDTH_M = 1.0
_MOTORCYCLE_DEPTH_M = 2.5

_DEFAULT_PARKING_RATIO = 1.0
_DEFAULT_ACCESSIBLE_RATIO = 0.05
_DEFAULT_LANE_WIDTH_M = 5.0
_DEFAULT_TURNING_RADIUS_M = 6.0
_DEFAULT_RAMP_WIDTH_M = 3.5
_DEFAULT_RAMP_LENGTH_M = 12.0
_DEFAULT_RAMP_SLOPE_PCT = 15.0

_EPS = 1e-6
_DM_PER_M = 10


@dataclass(frozen=True)
class _LaneBand:
    lane_id: str
    side: str
    interval_start: float
    interval_end: float
    lane_center_y: float

    @property
    def length_m(self) -> float:
        return max(0.0, self.interval_end - self.interval_start)


@dataclass
class _TemplateLayout:
    storey: ParkingStorey
    total_spaces: int
    accessible_spaces: int
    motorcycle_spaces: int


def solve_parking(
    solar: Solar,
    residential_solution: Solution,
    floor_height_m: float,
    parking_spaces_per_unit: float = _DEFAULT_PARKING_RATIO,
    accessible_ratio: float = _DEFAULT_ACCESSIBLE_RATIO,
    lane_width_m: float = _DEFAULT_LANE_WIDTH_M,
    turning_radius_m: float = _DEFAULT_TURNING_RADIUS_M,
    ramp_width_m: float = _DEFAULT_RAMP_WIDTH_M,
    ramp_length_m: float = _DEFAULT_RAMP_LENGTH_M,
    ramp_slope_pct: float = _DEFAULT_RAMP_SLOPE_PCT,
) -> ParkingSolution:
    """Genera una planta de aparcamiento subterráneo conectada a la rampa."""
    t_start = time.perf_counter()

    try:
        return _solve_parking_internal(
            solar=solar,
            residential_solution=residential_solution,
            floor_height_m=floor_height_m,
            parking_spaces_per_unit=parking_spaces_per_unit,
            accessible_ratio=accessible_ratio,
            lane_width_m=lane_width_m,
            turning_radius_m=turning_radius_m,
            ramp_width_m=ramp_width_m,
            ramp_length_m=ramp_length_m,
            ramp_slope_pct=ramp_slope_pct,
            t_start=t_start,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t_start
        return ParkingSolution(
            status=SolutionStatus.ERROR,
            storey=None,
            metrics=ParkingSolutionMetrics(
                total_spaces=0,
                standard_spaces=0,
                accessible_spaces=0,
                motorcycle_spaces=0,
                required_spaces=0,
            ),
            solver_time_seconds=elapsed,
            message=str(exc),
        )


def _solve_parking_internal(
    solar: Solar,
    residential_solution: Solution,
    floor_height_m: float,
    parking_spaces_per_unit: float,
    accessible_ratio: float,
    lane_width_m: float,
    turning_radius_m: float,
    ramp_width_m: float,
    ramp_length_m: float,
    ramp_slope_pct: float,
    t_start: float,
) -> ParkingSolution:
    if parking_spaces_per_unit < 0.0:
        raise ValueError("parking_spaces_per_unit debe ser >= 0")
    if not 0.0 <= accessible_ratio <= 1.0:
        raise ValueError("accessible_ratio debe estar en [0, 1]")

    required_spaces = math.ceil(len(residential_solution.placements) * parking_spaces_per_unit)
    if required_spaces == 0:
        elapsed = time.perf_counter() - t_start
        return ParkingSolution(
            status=SolutionStatus.FEASIBLE,
            storey=None,
            metrics=ParkingSolutionMetrics(
                total_spaces=0,
                standard_spaces=0,
                accessible_spaces=0,
                motorcycle_spaces=0,
                required_spaces=0,
            ),
            solver_time_seconds=elapsed,
            message="No se requiere aparcamiento para el programa actual.",
        )

    obstacles = [_core_to_rectangle(core) for core in residential_solution.communication_cores]
    templates = [
        ("left", "bottom"),
        ("right", "bottom"),
        ("left", "top"),
        ("right", "top"),
    ]

    best_layout: _TemplateLayout | None = None
    for side, vertical_anchor in templates:
        layout = _evaluate_template(
            solar=solar,
            floor_height_m=floor_height_m,
            obstacles=obstacles,
            side=side,
            vertical_anchor=vertical_anchor,
            accessible_ratio=accessible_ratio,
            lane_width_m=lane_width_m,
            turning_radius_m=turning_radius_m,
            ramp_width_m=ramp_width_m,
            ramp_length_m=ramp_length_m,
            ramp_slope_pct=ramp_slope_pct,
        )
        if layout is None:
            continue
        if best_layout is None or layout.total_spaces > best_layout.total_spaces:
            best_layout = layout

    elapsed = time.perf_counter() - t_start
    if best_layout is None or best_layout.total_spaces == 0:
        return ParkingSolution(
            status=SolutionStatus.INFEASIBLE,
            storey=None,
            metrics=ParkingSolutionMetrics(
                total_spaces=0,
                standard_spaces=0,
                accessible_spaces=0,
                motorcycle_spaces=0,
                required_spaces=required_spaces,
            ),
            solver_time_seconds=elapsed,
            message="No se encontró una plantilla de aparcamiento conectada y válida.",
        )

    standard_spaces = sum(
        1 for s in best_layout.storey.spaces if s.type == ParkingSpaceType.STANDARD
    )
    accessible_spaces = sum(
        1 for s in best_layout.storey.spaces if s.type == ParkingSpaceType.ACCESSIBLE
    )
    motorcycle_spaces = sum(
        1 for s in best_layout.storey.spaces if s.type == ParkingSpaceType.MOTORCYCLE
    )

    status = (
        SolutionStatus.OPTIMAL
        if best_layout.total_spaces >= required_spaces
        else SolutionStatus.FEASIBLE
    )
    message = (
        f"Capacidad generada: {best_layout.total_spaces} plazas; exigidas: {required_spaces}."
    )

    return ParkingSolution(
        status=status,
        storey=best_layout.storey,
        metrics=ParkingSolutionMetrics(
            total_spaces=best_layout.total_spaces,
            standard_spaces=standard_spaces,
            accessible_spaces=accessible_spaces,
            motorcycle_spaces=motorcycle_spaces,
            required_spaces=required_spaces,
        ),
        solver_time_seconds=elapsed,
        message=message,
    )


def _evaluate_template(
    solar: Solar,
    floor_height_m: float,
    obstacles: list[Rectangle],
    side: str,
    vertical_anchor: str,
    accessible_ratio: float,
    lane_width_m: float,
    turning_radius_m: float,
    ramp_width_m: float,
    ramp_length_m: float,
    ramp_slope_pct: float,
) -> _TemplateLayout | None:
    min_x, min_y, max_x, max_y = solar.contour.bounding_box
    parking_depth_m = _STANDARD_DEPTH_M
    module_height = parking_depth_m * 2.0 + lane_width_m
    first_module_offset = ramp_length_m + turning_radius_m

    spine_x_min, spine_x_max = _spine_bounds(min_x, max_x, side, lane_width_m)
    spine_y_min, spine_y_max = _spine_vertical_bounds(min_y, max_y, vertical_anchor, ramp_length_m)
    spine_rect = Rectangle(
        x=spine_x_min,
        y=spine_y_min,
        width=spine_x_max - spine_x_min,
        height=spine_y_max - spine_y_min,
    )

    ramp_rect, ramp_access = _build_ramp(
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        side=side,
        vertical_anchor=vertical_anchor,
        ramp_width_m=ramp_width_m,
        ramp_length_m=ramp_length_m,
        ramp_slope_pct=ramp_slope_pct,
    )

    if any(_rectangles_overlap(spine_rect, obstacle) for obstacle in obstacles):
        return None
    if any(_rectangles_overlap(ramp_rect, obstacle) for obstacle in obstacles):
        return None

    if vertical_anchor == "bottom":
        available_height = max_y - (min_y + first_module_offset)
    else:
        available_height = (max_y - first_module_offset) - min_y

    num_modules = math.floor(available_height / module_height)
    if num_modules < 1:
        return None

    spine_center_x = (spine_x_min + spine_x_max) / 2.0
    spine_lane_id = f"lane-spine-{side}-{vertical_anchor}"

    cross_lanes: list[ParkingLane] = []
    bands: list[_LaneBand] = []
    cross_lane_ids: list[str] = []
    for module_index in range(num_modules):
        if vertical_anchor == "bottom":
            module_base = min_y + first_module_offset + module_index * module_height
            lane_center_y = module_base + parking_depth_m + lane_width_m / 2.0
        else:
            module_top = max_y - first_module_offset - module_index * module_height
            lane_center_y = module_top - parking_depth_m - lane_width_m / 2.0

        lane_id = f"lane-{side}-{vertical_anchor}-{module_index}"
        cross_lane_ids.append(lane_id)
        lane_end_x = max_x if side == "left" else min_x
        cross_lanes.append(
            ParkingLane(
                id=lane_id,
                points=[
                    Point2D(x=spine_center_x, y=lane_center_y),
                    Point2D(x=lane_end_x, y=lane_center_y),
                ],
                width_m=lane_width_m,
                connected_lane_ids=[spine_lane_id],
            )
        )

        top_band = _connected_band(
            lane_id=lane_id,
            side="top",
            lane_center_y=lane_center_y,
            lane_width_m=lane_width_m,
            side_anchor=side,
            cross_start_x=spine_x_max if side == "left" else min_x,
            cross_end_x=max_x if side == "left" else spine_x_min,
            obstacles=obstacles,
        )
        bottom_band = _connected_band(
            lane_id=lane_id,
            side="bottom",
            lane_center_y=lane_center_y,
            lane_width_m=lane_width_m,
            side_anchor=side,
            cross_start_x=spine_x_max if side == "left" else min_x,
            cross_end_x=max_x if side == "left" else spine_x_min,
            obstacles=obstacles,
        )
        if top_band.length_m > 0:
            bands.append(top_band)
        if bottom_band.length_m > 0:
            bands.append(bottom_band)

    if not bands:
        return None

    band_solution = _solve_band_mix(bands, accessible_ratio)
    if band_solution is None:
        return None

    spaces = _build_parking_spaces(
        bands=bands,
        standard_counts=band_solution[0],
        accessible_counts=band_solution[1],
        lane_width_m=lane_width_m,
        floor_level=-1,
        side_anchor=side,
        accessible_ratio=accessible_ratio,
    )

    spine_lane = ParkingLane(
        id=spine_lane_id,
        points=[
            Point2D(x=spine_center_x, y=spine_y_min),
            Point2D(x=spine_center_x, y=spine_y_max),
        ],
        width_m=lane_width_m,
        connected_lane_ids=cross_lane_ids,
    )
    lanes = [spine_lane] + cross_lanes
    ramp_access.connected_lane_id = spine_lane_id

    parking_storey = ParkingStorey(
        id=f"parking-storey-{side}-{vertical_anchor}",
        level=-1,
        elevation_m=-floor_height_m,
        height_m=floor_height_m,
        name="Aparcamiento sótano",
        spaces=spaces,
        lanes=lanes,
        ramp_access=ramp_access,
    )
    return _TemplateLayout(
        storey=parking_storey,
        total_spaces=len(spaces),
        accessible_spaces=sum(1 for s in spaces if s.type == ParkingSpaceType.ACCESSIBLE),
        motorcycle_spaces=sum(1 for s in spaces if s.type == ParkingSpaceType.MOTORCYCLE),
    )


def _solve_band_mix(
    bands: list[_LaneBand],
    accessible_ratio: float,
) -> tuple[list[int], list[int]] | None:
    model = cp_model.CpModel()
    standard_vars: list[cp_model.IntVar] = []
    accessible_vars: list[cp_model.IntVar] = []

    for idx, band in enumerate(bands):
        length_dm = math.floor(band.length_m * _DM_PER_M + _EPS)
        standard = model.NewIntVar(0, length_dm // 25, f"std_{idx}")
        accessible = model.NewIntVar(0, length_dm // 36, f"acc_{idx}")
        model.Add(25 * standard + 36 * accessible <= length_dm)
        standard_vars.append(standard)
        accessible_vars.append(accessible)

    total_standard = sum(standard_vars)
    total_accessible = sum(accessible_vars)
    total_car_spaces = total_standard + total_accessible

    accessible_pct = math.ceil(accessible_ratio * 100)
    if accessible_pct > 0:
        model.Add(100 * total_accessible >= accessible_pct * total_car_spaces)

    model.Maximize(total_car_spaces)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status_code = solver.Solve(model)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return [solver.Value(v) for v in standard_vars], [solver.Value(v) for v in accessible_vars]


def _build_parking_spaces(
    bands: list[_LaneBand],
    standard_counts: list[int],
    accessible_counts: list[int],
    lane_width_m: float,
    floor_level: int,
    side_anchor: str,
    accessible_ratio: float,
) -> list[ParkingSpace]:
    residual_motorcycles: list[int] = []
    for band, std_count, acc_count in zip(bands, standard_counts, accessible_counts, strict=True):
        residual = band.length_m - std_count * _STANDARD_WIDTH_M - acc_count * _ACCESSIBLE_WIDTH_M
        residual_motorcycles.append(max(0, math.floor((residual + _EPS) / _MOTORCYCLE_WIDTH_M)))

    total_accessible = sum(accessible_counts)
    total_car_spaces = sum(standard_counts) + total_accessible
    total_residual_moto = sum(residual_motorcycles)
    if accessible_ratio > 0 and total_accessible > 0:
        max_total_spaces = math.floor(total_accessible / accessible_ratio)
        allowed_motorcycles = max(0, min(total_residual_moto, max_total_spaces - total_car_spaces))
    elif accessible_ratio == 0.0:
        allowed_motorcycles = total_residual_moto
    else:
        allowed_motorcycles = 0

    spaces: list[ParkingSpace] = []
    space_idx = 0
    motorcycles_left = allowed_motorcycles

    for band, std_count, acc_count, moto_capacity in zip(
        bands, standard_counts, accessible_counts, residual_motorcycles, strict=True
    ):
        cursor = band.interval_start if side_anchor == "left" else band.interval_end
        cursor = _place_spaces_of_type(
            spaces=spaces,
            count=acc_count,
            dimensions=_dimensions_for_type(ParkingSpaceType.ACCESSIBLE),
            space_type=ParkingSpaceType.ACCESSIBLE,
            band=band,
            lane_width_m=lane_width_m,
            floor_level=floor_level,
            space_idx_ref=[space_idx],
            cursor=cursor,
            side_anchor=side_anchor,
        )
        space_idx = len(spaces)
        cursor = _place_spaces_of_type(
            spaces=spaces,
            count=std_count,
            dimensions=_dimensions_for_type(ParkingSpaceType.STANDARD),
            space_type=ParkingSpaceType.STANDARD,
            band=band,
            lane_width_m=lane_width_m,
            floor_level=floor_level,
            space_idx_ref=[space_idx],
            cursor=cursor,
            side_anchor=side_anchor,
        )
        space_idx = len(spaces)

        motos_here = min(moto_capacity, motorcycles_left)
        if motos_here > 0:
            _place_spaces_of_type(
                spaces=spaces,
                count=motos_here,
                dimensions=_dimensions_for_type(ParkingSpaceType.MOTORCYCLE),
                space_type=ParkingSpaceType.MOTORCYCLE,
                band=band,
                lane_width_m=lane_width_m,
                floor_level=floor_level,
                space_idx_ref=[space_idx],
                cursor=cursor,
                side_anchor=side_anchor,
            )
            space_idx = len(spaces)
            motorcycles_left -= motos_here

    return spaces


def _place_spaces_of_type(
    spaces: list[ParkingSpace],
    count: int,
    dimensions: ParkingDimensions,
    space_type: ParkingSpaceType,
    band: _LaneBand,
    lane_width_m: float,
    floor_level: int,
    space_idx_ref: list[int],
    cursor: float,
    side_anchor: str,
) -> float:
    for _ in range(count):
        if side_anchor == "left":
            x_min = cursor
            x_max = cursor + dimensions.width_m
            cursor = x_max
        else:
            x_max = cursor
            x_min = cursor - dimensions.width_m
            cursor = x_min

        if band.side == "top":
            y_min = band.lane_center_y + lane_width_m / 2.0
            y_max = y_min + dimensions.depth_m
        else:
            y_max = band.lane_center_y - lane_width_m / 2.0
            y_min = y_max - dimensions.depth_m

        polygon = Polygon2D(
            points=[
                Point2D(x=x_min, y=y_min),
                Point2D(x=x_max, y=y_min),
                Point2D(x=x_max, y=y_max),
                Point2D(x=x_min, y=y_max),
            ]
        )
        spaces.append(
            ParkingSpace(
                id=f"parking-space-{space_idx_ref[0]}",
                name=f"Plaza {space_type.value.lower()} {space_idx_ref[0]}",
                contour=polygon,
                floor_level=floor_level,
                dimensions=dimensions,
                type=space_type,
                lane_id=band.lane_id,
            )
        )
        space_idx_ref[0] += 1
    return cursor


def _connected_band(
    lane_id: str,
    side: str,
    lane_center_y: float,
    lane_width_m: float,
    side_anchor: str,
    cross_start_x: float,
    cross_end_x: float,
    obstacles: list[Rectangle],
) -> _LaneBand:
    if side == "top":
        band_y_min = lane_center_y + lane_width_m / 2.0
        band_y_max = band_y_min + _STANDARD_DEPTH_M
    else:
        band_y_max = lane_center_y - lane_width_m / 2.0
        band_y_min = band_y_max - _STANDARD_DEPTH_M

    interval_start = cross_start_x
    interval_end = cross_end_x

    if side_anchor == "left":
        for obstacle in obstacles:
            if _overlaps_y_band(obstacle, band_y_min, band_y_max) and obstacle.x >= interval_start:
                interval_end = min(interval_end, obstacle.x)
    else:
        for obstacle in obstacles:
            obstacle_end = obstacle.x + obstacle.width
            if _overlaps_y_band(obstacle, band_y_min, band_y_max) and obstacle_end <= interval_end:
                interval_start = max(interval_start, obstacle_end)

    if interval_start >= interval_end - _EPS:
        interval_start = interval_end

    return _LaneBand(
        lane_id=lane_id,
        side=side,
        interval_start=interval_start,
        interval_end=interval_end,
        lane_center_y=lane_center_y,
    )


def _build_ramp(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    side: str,
    vertical_anchor: str,
    ramp_width_m: float,
    ramp_length_m: float,
    ramp_slope_pct: float,
) -> tuple[Rectangle, RampAccess]:
    if side == "left":
        x_min = min_x
        x_center = x_min + ramp_width_m / 2.0
    else:
        x_min = max_x - ramp_width_m
        x_center = x_min + ramp_width_m / 2.0

    if vertical_anchor == "bottom":
        y_min = min_y
        y_max = min_y + ramp_length_m
        start_point = Point2D(x=x_center, y=y_min)
        end_point = Point2D(x=x_center, y=y_max)
    else:
        y_max = max_y
        y_min = max_y - ramp_length_m
        start_point = Point2D(x=x_center, y=y_max)
        end_point = Point2D(x=x_center, y=y_min)

    ramp = Rectangle(x=x_min, y=y_min, width=ramp_width_m, height=ramp_length_m)
    ramp_access = RampAccess(
        id=f"ramp-{side}-{vertical_anchor}",
        start_point=start_point,
        end_point=end_point,
        width_m=ramp_width_m,
        slope_pct=ramp_slope_pct,
        connected_lane_id="",
    )
    return ramp, ramp_access


def _spine_bounds(
    min_x: float, max_x: float, side: str, lane_width_m: float
) -> tuple[float, float]:
    if side == "left":
        return min_x, min_x + lane_width_m
    return max_x - lane_width_m, max_x


def _spine_vertical_bounds(
    min_y: float,
    max_y: float,
    vertical_anchor: str,
    ramp_length_m: float,
) -> tuple[float, float]:
    if vertical_anchor == "bottom":
        return min_y + ramp_length_m, max_y
    return min_y, max_y - ramp_length_m


def _dimensions_for_type(space_type: ParkingSpaceType) -> ParkingDimensions:
    if space_type == ParkingSpaceType.STANDARD:
        return ParkingDimensions(width_m=_STANDARD_WIDTH_M, depth_m=_STANDARD_DEPTH_M)
    if space_type == ParkingSpaceType.ACCESSIBLE:
        return ParkingDimensions(width_m=_ACCESSIBLE_WIDTH_M, depth_m=_ACCESSIBLE_DEPTH_M)
    return ParkingDimensions(width_m=_MOTORCYCLE_WIDTH_M, depth_m=_MOTORCYCLE_DEPTH_M)


def _core_to_rectangle(core: CommunicationCore) -> Rectangle:
    return Rectangle(
        x=core.position.x,
        y=core.position.y,
        width=core.width_m,
        height=core.depth_m,
    )


def _overlaps_y_band(rect: Rectangle, band_y_min: float, band_y_max: float) -> bool:
    return not (rect.y + rect.height <= band_y_min + _EPS or rect.y >= band_y_max - _EPS)


def _rectangles_overlap(a: Rectangle, b: Rectangle) -> bool:
    a_right = a.x + a.width
    b_right = b.x + b.width
    a_top = a.y + a.height
    b_top = b.y + b.height
    return not (
        a_right <= b.x + _EPS
        or b_right <= a.x + _EPS
        or a_top <= b.y + _EPS
        or b_top <= a.y + _EPS
    )
