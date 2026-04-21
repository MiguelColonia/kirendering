"""Motor de optimización espacial multi-planta con OR-Tools CP-SAT.

Modelo actual (Fase 3):

- Distribución residencial en múltiples plantas usando ``Program.num_floors``.
- Núcleos de comunicación vertical compartidos entre plantas:
    misma posición en planta para todos los niveles servidos.
- Restricción de recorrido de evacuación simplificada:
    cada unidad debe estar a distancia Manhattan máxima de al menos un núcleo.
- No solapamiento entre unidades de la misma planta y entre unidades y núcleos.

La discretización sigue usando rejilla regular (por defecto 0,5 m).
"""

import math
import time

from ortools.sat.python import cp_model
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import box as shapely_box
from shapely.prepared import prep

from cimiento.schemas import Program, Solar, Solution, Typology
from cimiento.schemas.architectural import CommunicationCore
from cimiento.schemas.geometry_primitives import Rectangle
from cimiento.schemas.solution import SolutionMetrics, SolutionStatus, UnitPlacement

_DEFAULT_GRID_RESOLUTION_M: float = 0.5  # metros por celda
_DEFAULT_UNITS_PER_CORE_PER_FLOOR: int = 8
_DEFAULT_MAX_DISTANCE_TO_CORE_M: float = 25.0
_DEFAULT_CORE_WIDTH_M: float = 4.0
_DEFAULT_CORE_DEPTH_M: float = 6.0
_DEFAULT_CORE_HAS_ELEVATOR: bool = True

_CP_STATUS_MAP = {
    cp_model.OPTIMAL: SolutionStatus.OPTIMAL,
    cp_model.FEASIBLE: SolutionStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolutionStatus.INFEASIBLE,
    cp_model.UNKNOWN: SolutionStatus.TIMEOUT,
}


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _canonical_shape_cells(typology: Typology, grid_resolution_m: float) -> tuple[int, int]:
    """
    Devuelve (w_cells, h_cells) — la forma canónica de la tipología en celdas de rejilla.

    Se parte de un ancho estándar de 7 m y se ajusta la altura para que el área
    resultante sea >= min_useful_area. El resultado es determinista.

    # TODO Fase 3: reemplazar por variables CP-SAT con AddMultiplicationEquality.
    """
    cell_area = grid_resolution_m**2
    w_cells = round(7.0 / grid_resolution_m)
    h_cells = math.ceil(typology.min_useful_area / (w_cells * cell_area))
    # Ajuste de seguridad ante redondeos
    while w_cells * h_cells * cell_area < typology.min_useful_area:
        h_cells += 1
    return w_cells, h_cells


def _valid_placements_for_shape(
    solar_poly: ShapelyPolygon,
    min_x: float,
    min_y: float,
    solar_w_cells: int,
    solar_h_cells: int,
    grid_resolution_m: float,
    w_cells: int,
    h_cells: int,
) -> list[tuple[int, int]]:
    """
    Devuelve todas las posiciones (cx, cy) desde las que una unidad de w_cells×h_cells
    celdas queda completamente dentro del polígono del solar.

    Usa Shapely `prepared_polygon.covers(unit_rect)` para comprobar que cada
    candidato de posición contiene su rectángulo completamente dentro del solar.
    Soporta polígonos convexos y cóncavos (L, U, T…). Ver ADR 0006.

    La lista resultante se pasa directamente a `AddAllowedAssignments` en CP-SAT.
    """
    res = grid_resolution_m
    prepared = prep(solar_poly)
    valid: list[tuple[int, int]] = []
    for cy in range(solar_h_cells - h_cells + 1):
        for cx in range(solar_w_cells - w_cells + 1):
            unit_rect = shapely_box(
                min_x + cx * res,
                min_y + cy * res,
                min_x + (cx + w_cells) * res,
                min_y + (cy + h_cells) * res,
            )
            if prepared.covers(unit_rect):
                valid.append((cx, cy))
    return valid


def _empty_solution(elapsed: float) -> Solution:
    """Solución vacía FEASIBLE para programas sin unidades solicitadas."""
    return Solution(
        status=SolutionStatus.FEASIBLE,
        placements=[],
        communication_cores=[],
        metrics=SolutionMetrics(
            total_assigned_area=0.0,
            num_units_placed=0,
            typology_fulfillment={},
        ),
        solver_time_seconds=elapsed,
    )


def _infeasible_solution(message: str, elapsed: float) -> Solution:
    """Solución INFEASIBLE con mensaje descriptivo y cero colocaciones."""
    return Solution(
        status=SolutionStatus.INFEASIBLE,
        placements=[],
        communication_cores=[],
        metrics=SolutionMetrics(
            total_assigned_area=0.0,
            num_units_placed=0,
            typology_fulfillment={},
        ),
        solver_time_seconds=elapsed,
        message=message,
    )


def _error_solution(message: str, elapsed: float) -> Solution:
    """Solución ERROR con descripción de la excepción."""
    return Solution(
        status=SolutionStatus.ERROR,
        placements=[],
        communication_cores=[],
        metrics=SolutionMetrics(
            total_assigned_area=0.0,
            num_units_placed=0,
            typology_fulfillment={},
        ),
        solver_time_seconds=elapsed,
        message=message,
    )


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def solve(
    solar: Solar,
    program: Program,
    timeout_seconds: int = 60,
    grid_resolution_m: float = _DEFAULT_GRID_RESOLUTION_M,
    units_per_core_per_floor: int = _DEFAULT_UNITS_PER_CORE_PER_FLOOR,
    max_distance_to_core_m: float = _DEFAULT_MAX_DISTANCE_TO_CORE_M,
    core_width_m: float = _DEFAULT_CORE_WIDTH_M,
    core_depth_m: float = _DEFAULT_CORE_DEPTH_M,
    core_has_elevator: bool = _DEFAULT_CORE_HAS_ELEVATOR,
) -> Solution:
    """
    Distribuye las unidades del programa sobre el solar usando OR-Tools CP-SAT.

    Parámetros
    ----------
    solar:
        Terreno con su contorno poligonal y condiciones urbanísticas.
    program:
        Mix de tipologías con el número de unidades requeridas por tipo en todo el edificio.
    timeout_seconds:
        Tiempo máximo de resolución en segundos (por defecto 60).
    grid_resolution_m:
        Resolución de la rejilla de discretización en metros (por defecto 0,5 m).
    units_per_core_per_floor:
        Capacidad objetivo de un núcleo por planta (por defecto 8).
    max_distance_to_core_m:
        Distancia Manhattan máxima permitida entre centro de unidad y centro de núcleo.
    core_width_m, core_depth_m:
        Dimensiones en planta del núcleo tipo.
    core_has_elevator:
        Si es True, cada núcleo incluye ascensor además de escalera.

    Devuelve
    --------
    Solution con status, colocaciones y métricas.

    Ejemplo
    -------
    >>> from cimiento.schemas import Solar, Program, Typology, ...
    >>> solution = solve(solar, program, timeout_seconds=30)
    >>> print(solution.status, solution.metrics.num_units_placed)
    """
    t_start = time.perf_counter()

    try:
        return _solve_internal(
            solar,
            program,
            timeout_seconds,
            grid_resolution_m,
            units_per_core_per_floor,
            max_distance_to_core_m,
            core_width_m,
            core_depth_m,
            core_has_elevator,
            t_start,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        return _error_solution(str(exc), elapsed)


def _solve_internal(
    solar: Solar,
    program: Program,
    timeout_seconds: int,
    grid_resolution_m: float,
    units_per_core_per_floor: int,
    max_distance_to_core_m: float,
    core_width_m: float,
    core_depth_m: float,
    core_has_elevator: bool,
    t_start: float,
) -> Solution:
    # --- Caso borde: programa vacío ---
    total_units = sum(entry.count for entry in program.mix)
    if total_units == 0:
        return _empty_solution(time.perf_counter() - t_start)

    if units_per_core_per_floor < 1:
        raise ValueError("units_per_core_per_floor debe ser >= 1")

    # --- Discretización del solar (bbox axialmente alineada) ---
    min_x, min_y, max_x, max_y = solar.contour.bounding_box
    solar_w_cells = round((max_x - min_x) / grid_resolution_m)
    solar_h_cells = round((max_y - min_y) / grid_resolution_m)

    # Polígono Shapely del solar para confinamiento poligonal (C1)
    solar_poly = ShapelyPolygon([(p.x, p.y) for p in solar.contour.points])

    # --- Lookup de tipologías y lista plana de unidades ---
    typology_map: dict[str, Typology] = {t.id: t for t in program.typologies}

    # Cada entrada es (typology_id, w_cells, h_cells, floor)
    units: list[tuple[str, int, int, int]] = []
    unit_counter = 0
    for entry in program.mix:
        typology = typology_map[entry.typology_id]
        w, h = _canonical_shape_cells(typology, grid_resolution_m)
        for _ in range(entry.count):
            floor = unit_counter % program.num_floors
            units.append((entry.typology_id, w, h, floor))
            unit_counter += 1

    units_per_floor = [0] * program.num_floors
    for _, _, _, floor in units:
        units_per_floor[floor] += 1

    required_cores = max(1, math.ceil(max(units_per_floor) / units_per_core_per_floor))

    core_w_cells = max(1, round(core_width_m / grid_resolution_m))
    core_h_cells = max(1, round(core_depth_m / grid_resolution_m))

    # --- Detección rápida de inviabilidad geométrica (unidades > bbox) ---
    oversized = [
        (tid, w, h)
        for tid, w, h, _ in units
        if w > solar_w_cells or h > solar_h_cells
    ]
    if oversized:
        elapsed = time.perf_counter() - t_start
        return _infeasible_solution(
            f"Unidades de tipología '{oversized[0][0]}' "
            f"({oversized[0][1] * grid_resolution_m:.1f} m × "
            f"{oversized[0][2] * grid_resolution_m:.1f} m) "
            f"no caben en el solar "
            f"({solar_w_cells * grid_resolution_m:.1f} m × "
            f"{solar_h_cells * grid_resolution_m:.1f} m).",
            elapsed,
        )

    if core_w_cells > solar_w_cells or core_h_cells > solar_h_cells:
        elapsed = time.perf_counter() - t_start
        return _infeasible_solution(
            "El núcleo de comunicación no cabe en el solar con las dimensiones configuradas.",
            elapsed,
        )

    # --- (C1) Precomputar posiciones válidas por forma (w, h) ---
    # Cada clave es (w, h); su valor es la lista de (cx, cy) tal que la unidad queda
    # completamente dentro del polígono del solar. Se calcula una vez por forma.
    shape_to_valid: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for _, w, h, _ in units:
        if (w, h) not in shape_to_valid:
            shape_to_valid[(w, h)] = _valid_placements_for_shape(
                solar_poly, min_x, min_y,
                solar_w_cells, solar_h_cells,
                grid_resolution_m, w, h,
            )

    core_valid_positions = _valid_placements_for_shape(
        solar_poly,
        min_x,
        min_y,
        solar_w_cells,
        solar_h_cells,
        grid_resolution_m,
        core_w_cells,
        core_h_cells,
    )

    # Inviabilidad temprana: algún tipo de unidad no tiene posición válida en el solar
    for (w, h), valid_pos in shape_to_valid.items():
        if not valid_pos:
            elapsed = time.perf_counter() - t_start
            return _infeasible_solution(
                f"Ninguna posición válida para una unidad de "
                f"{w * grid_resolution_m:.1f} m × {h * grid_resolution_m:.1f} m "
                "dentro del polígono del solar.",
                elapsed,
            )

    if not core_valid_positions:
        elapsed = time.perf_counter() - t_start
        return _infeasible_solution(
            "No existen posiciones válidas para el núcleo de comunicación dentro del solar.",
            elapsed,
        )

    # --- Construcción del modelo CP-SAT ---
    model = cp_model.CpModel()

    x_vars: list[cp_model.IntVar] = []
    y_vars: list[cp_model.IntVar] = []
    x_intervals_by_floor: dict[int, list[cp_model.IntervalVar]] = {
        floor: [] for floor in range(program.num_floors)
    }
    y_intervals_by_floor: dict[int, list[cp_model.IntervalVar]] = {
        floor: [] for floor in range(program.num_floors)
    }

    for i, (_, w, h, floor) in enumerate(units):
        # Dominio: bbox del solar (restricción holgada; la tabla de posiciones es más estricta)
        x = model.NewIntVar(0, solar_w_cells - w, f"x_{i}")
        y = model.NewIntVar(0, solar_h_cells - h, f"y_{i}")

        x_end = model.NewIntVar(w, solar_w_cells, f"x_end_{i}")
        y_end = model.NewIntVar(h, solar_h_cells, f"y_end_{i}")
        model.Add(x_end == x + w)
        model.Add(y_end == y + h)

        x_intervals_by_floor[floor].append(model.NewIntervalVar(x, w, x_end, f"ix_{i}"))
        y_intervals_by_floor[floor].append(model.NewIntervalVar(y, h, y_end, f"iy_{i}"))
        x_vars.append(x)
        y_vars.append(y)

        # (C1) Confinamiento poligonal: (x_i, y_i) debe estar en las posiciones permitidas
        model.AddAllowedAssignments([x, y], shape_to_valid[(w, h)])

    core_x_vars: list[cp_model.IntVar] = []
    core_y_vars: list[cp_model.IntVar] = []
    core_x_intervals: list[cp_model.IntervalVar] = []
    core_y_intervals: list[cp_model.IntervalVar] = []

    for c in range(required_cores):
        core_x = model.NewIntVar(0, solar_w_cells - core_w_cells, f"core_x_{c}")
        core_y = model.NewIntVar(0, solar_h_cells - core_h_cells, f"core_y_{c}")
        core_x_end = model.NewIntVar(core_w_cells, solar_w_cells, f"core_x_end_{c}")
        core_y_end = model.NewIntVar(core_h_cells, solar_h_cells, f"core_y_end_{c}")
        model.Add(core_x_end == core_x + core_w_cells)
        model.Add(core_y_end == core_y + core_h_cells)

        core_x_intervals.append(
            model.NewIntervalVar(core_x, core_w_cells, core_x_end, f"core_ix_{c}")
        )
        core_y_intervals.append(
            model.NewIntervalVar(core_y, core_h_cells, core_y_end, f"core_iy_{c}")
        )
        core_x_vars.append(core_x)
        core_y_vars.append(core_y)
        model.AddAllowedAssignments([core_x, core_y], core_valid_positions)

    # Los núcleos no pueden solaparse entre sí.
    model.AddNoOverlap2D(core_x_intervals, core_y_intervals)

    # (C2) No solapamiento por planta entre unidades y núcleos.
    for floor in range(program.num_floors):
        model.AddNoOverlap2D(
            x_intervals_by_floor[floor] + core_x_intervals,
            y_intervals_by_floor[floor] + core_y_intervals,
        )

    # Distancia máxima unidad-núcleo (recorrido de evacuación simplificado).
    max_dist_cells = math.ceil(max_distance_to_core_m / grid_resolution_m)
    max_dist_double_cells = 2 * max_dist_cells
    max_dx = 2 * solar_w_cells
    max_dy = 2 * solar_h_cells

    for i, (_, w, h, _) in enumerate(units):
        unit_center_x2 = 2 * x_vars[i] + w
        unit_center_y2 = 2 * y_vars[i] + h
        reaches_any_core: list[cp_model.BoolVar] = []

        for c in range(required_cores):
            core_center_x2 = 2 * core_x_vars[c] + core_w_cells
            core_center_y2 = 2 * core_y_vars[c] + core_h_cells

            dx = model.NewIntVar(0, max_dx, f"dx_u{i}_c{c}")
            dy = model.NewIntVar(0, max_dy, f"dy_u{i}_c{c}")
            model.AddAbsEquality(dx, unit_center_x2 - core_center_x2)
            model.AddAbsEquality(dy, unit_center_y2 - core_center_y2)

            reaches = model.NewBoolVar(f"reach_u{i}_c{c}")
            model.Add(dx + dy <= max_dist_double_cells).OnlyEnforceIf(reaches)
            model.Add(dx + dy >= max_dist_double_cells + 1).OnlyEnforceIf(reaches.Not())
            reaches_any_core.append(reaches)

        model.AddBoolOr(reaches_any_core)

    # Objetivo: maximizar suma de áreas asignadas
    # Con formas fijas cada área = w*h*cell_area es constante, por lo que el
    # objetivo equivale a colocar todas las unidades (satisfacibilidad estricta).
    cell_area = grid_resolution_m**2
    total_area_cells = sum(w * h for _, w, h, _ in units)
    model.Maximize(total_area_cells)  # constante: CP-SAT valida factibilidad

    # --- Resolución ---
    cp_solver = cp_model.CpSolver()
    cp_solver.parameters.max_time_in_seconds = timeout_seconds
    status_code = cp_solver.Solve(model)

    elapsed = time.perf_counter() - t_start
    cp_status = _CP_STATUS_MAP.get(status_code)

    if cp_status in (SolutionStatus.INFEASIBLE, SolutionStatus.TIMEOUT) or cp_status is None:
        message = (
            "El solver no encontró una distribución factible para todas las unidades "
            f"dentro del solar dado (tiempo: {elapsed:.2f} s)."
        )
        return Solution(
            status=cp_status or SolutionStatus.TIMEOUT,
            placements=[],
            metrics=SolutionMetrics(
                total_assigned_area=0.0,
                num_units_placed=0,
                typology_fulfillment={
                    tid: 0.0
                    for tid in {u[0] for u in units}
                },
            ),
            solver_time_seconds=elapsed,
            message=message,
        )

    # --- Construcción de placements ---
    placements: list[UnitPlacement] = []
    total_area_m2 = 0.0

    for i, (tid, w, h, floor) in enumerate(units):
        bbox = Rectangle(
            x=min_x + cp_solver.Value(x_vars[i]) * grid_resolution_m,
            y=min_y + cp_solver.Value(y_vars[i]) * grid_resolution_m,
            width=w * grid_resolution_m,
            height=h * grid_resolution_m,
        )
        placements.append(UnitPlacement(typology_id=tid, floor=floor, bbox=bbox))
        total_area_m2 += w * h * cell_area

    communication_cores: list[CommunicationCore] = []
    for c in range(required_cores):
        communication_cores.append(
            CommunicationCore(
                position={
                    "x": min_x + cp_solver.Value(core_x_vars[c]) * grid_resolution_m,
                    "y": min_y + cp_solver.Value(core_y_vars[c]) * grid_resolution_m,
                },
                width_m=core_w_cells * grid_resolution_m,
                depth_m=core_h_cells * grid_resolution_m,
                has_elevator=core_has_elevator,
                serves_floors=list(range(program.num_floors)),
            )
        )

    # Cumplimiento por tipología: unidades_colocadas / unidades_requeridas
    placed_by_type: dict[str, int] = {}
    for p in placements:
        placed_by_type[p.typology_id] = placed_by_type.get(p.typology_id, 0) + 1

    requested_by_type: dict[str, int] = {}
    for entry in program.mix:
        requested_by_type[entry.typology_id] = (
            requested_by_type.get(entry.typology_id, 0) + entry.count
        )

    typology_fulfillment = {
        tid: placed_by_type.get(tid, 0) / req
        for tid, req in requested_by_type.items()
    }

    return Solution(
        status=cp_status,
        placements=placements,
        communication_cores=communication_cores,
        metrics=SolutionMetrics(
            total_assigned_area=total_area_m2,
            num_units_placed=len(placements),
            typology_fulfillment=typology_fulfillment,
        ),
        solver_time_seconds=elapsed,
    )
