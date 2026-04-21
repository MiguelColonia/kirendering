"""
Tests del solver de distribución espacial — escritos ANTES de la implementación (TDD).

Definen el contrato observable de `solve`: dado un Solar y un Program, produce una
Solution con el status correcto, las colocaciones dentro del solar y sin solapamientos.
Fallarán con ImportError hasta que se implemente cimiento.solver.
"""

import pytest

from cimiento.schemas import Program, Rectangle, Solar, Solution, SolutionStatus, Typology

# Importación que fallará hasta que exista el módulo solver
from cimiento.solver import solve  # type: ignore[import]

pytest_plugins = ["tests.fixtures.valid_cases"]


# ---------------------------------------------------------------------------
# Helper: detección de solapamiento entre rectángulos
# ---------------------------------------------------------------------------


def _rectangles_overlap(a: Rectangle, b: Rectangle) -> bool:
    """
    Devuelve True si dos rectángulos se solapan (área de intersección > 0).
    El contacto en arista o esquina no se considera solapamiento.
    """
    a_right = a.x + a.width
    b_right = b.x + b.width
    a_top = a.y + a.height
    b_top = b.y + b.height
    return not (a_right <= b.x or b_right <= a.x or a_top <= b.y or b_top <= a.y)


def _core_rect(core) -> Rectangle:
    return Rectangle(
        x=core.position.x,
        y=core.position.y,
        width=core.width_m,
        height=core.depth_m,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_solver_feasible_simple_case(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Solar 20×30 m, programa de 5 unidades T2 (70 m² mín.).

    Invariantes:
    - Status FEASIBLE u OPTIMAL.
    - Exactamente 5 unidades colocadas.
    - Suma de áreas de bbox dentro del ±5 % de 5 × 70 = 350 m².
    - Ningún par de placements se solapa.
    """
    from cimiento.schemas import TypologyMix

    program = Program(
        project_id="test-simple",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )

    solution: Solution = solve(sample_solar_rectangular, program)

    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE), (
        f"Se esperaba OPTIMAL o FEASIBLE, obtenido: {solution.status}"
    )
    assert solution.metrics.num_units_placed == 5, (
        f"Se esperaban 5 unidades colocadas, obtenidas: {solution.metrics.num_units_placed}"
    )

    expected_area = 5 * sample_typology_t2.min_useful_area  # 350 m²
    total_area = sum(p.bbox.area for p in solution.placements)
    tolerance = 0.05 * expected_area
    assert abs(total_area - expected_area) <= tolerance, (
        f"Área total {total_area:.1f} m² fuera del ±5 % de {expected_area} m²"
    )

    # Sin solapamientos entre pares de placements
    for i, a in enumerate(solution.placements):
        for b in solution.placements[i + 1 :]:
            assert not _rectangles_overlap(a.bbox, b.bbox), (
                f"Solapamiento detectado entre unidades {i} y {i + 1}"
            )


def test_solver_infeasible_solar_too_small(
    sample_typology_t2: Typology,
) -> None:
    """
    Solar 5×5 m (25 m²) con programa de 10 T2 (700 m² requeridos).

    El solver debe reconocer la inviabilidad y devolver INFEASIBLE.
    """
    from cimiento.schemas import Point2D, Polygon2D, TypologyMix

    small_solar = Solar(
        id="solar-5x5",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=5.0, y=0.0),
                Point2D(x=5.0, y=5.0),
                Point2D(x=0.0, y=5.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )
    program = Program(
        project_id="test-infeasible",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=10)],
    )

    solution: Solution = solve(small_solar, program)

    assert solution.status == SolutionStatus.INFEASIBLE, (
        f"Se esperaba INFEASIBLE, obtenido: {solution.status}"
    )
    assert solution.metrics.num_units_placed == 0
    assert solution.message, "INFEASIBLE debe incluir un mensaje descriptivo"


def test_solver_respects_minimum_typology_area(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Cada placement debe tener bbox.area >= min_useful_area de su tipología.

    Garantiza que el solver nunca viola la restricción de área mínima.
    """
    from cimiento.schemas import TypologyMix

    program = Program(
        project_id="test-min-area",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )

    solution: Solution = solve(sample_solar_rectangular, program)

    for placement in solution.placements:
        assert placement.bbox.area >= sample_typology_t2.min_useful_area, (
            f"Unidad en planta {placement.floor} tiene {placement.bbox.area:.2f} m², "
            f"inferior al mínimo de {sample_typology_t2.min_useful_area} m²"
        )


def test_solver_respects_timeout(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Con timeout_seconds=1 el solver debe terminar en tiempo razonable.

    - solver_time_seconds debe ser <= 2 (margen de seguridad).
    - El status puede ser OPTIMAL, FEASIBLE o TIMEOUT, pero nunca ERROR.
    """
    from cimiento.schemas import TypologyMix

    program = Program(
        project_id="test-timeout",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )

    solution: Solution = solve(sample_solar_rectangular, program, timeout_seconds=1)

    assert solution.status != SolutionStatus.ERROR, (
        f"El solver devolvió ERROR: {solution.message}"
    )
    assert solution.solver_time_seconds <= 2.0, (
        f"El solver tardó {solution.solver_time_seconds:.2f} s, más del doble del timeout"
    )


def test_solver_empty_program_returns_empty_solution(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Un mix vacío no debe invocar al solver CP-SAT.

    Espera Solution FEASIBLE con cero unidades colocadas.
    """

    program = Program(
        project_id="test-empty",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[],  # programa sin unidades solicitadas
    )

    solution: Solution = solve(sample_solar_rectangular, program)

    assert solution.status == SolutionStatus.FEASIBLE
    assert solution.metrics.num_units_placed == 0
    assert solution.placements == []


def test_solver_multifloor_with_vertical_core_coherence(
    sample_typology_t2: Typology,
) -> None:
    """
    El solver debe usar varias plantas y generar núcleos verticalmente coherentes.

    Invariantes:
    - Se respeta Program.num_floors.
    - Existe al menos un núcleo con serves_floors para todas las plantas.
    - No hay solape entre núcleo y unidades en ninguna planta.
    """
    from cimiento.schemas import Point2D, Polygon2D, TypologyMix

    solar = Solar(
        id="solar-40x40",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=40.0, y=0.0),
                Point2D(x=40.0, y=40.0),
                Point2D(x=0.0, y=40.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=18.0,
    )

    program = Program(
        project_id="test-multifloor-core",
        num_floors=3,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=12)],
    )

    solution = solve(solar, program)

    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert len(solution.placements) == 12

    floors = sorted({p.floor for p in solution.placements})
    assert floors == [0, 1, 2]

    assert len(solution.communication_cores) >= 1
    for core in solution.communication_cores:
        assert core.serves_floors == [0, 1, 2]

    for placement in solution.placements:
        for core in solution.communication_cores:
            if placement.floor in core.serves_floors:
                assert not _rectangles_overlap(placement.bbox, _core_rect(core))


def test_solver_respects_max_distance_to_core(
    sample_typology_t2: Typology,
) -> None:
    """Cada unidad debe quedar a distancia Manhattan <= umbral respecto a un núcleo."""
    from cimiento.schemas import Point2D, Polygon2D, TypologyMix

    solar = Solar(
        id="solar-35x35",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=35.0, y=0.0),
                Point2D(x=35.0, y=35.0),
                Point2D(x=0.0, y=35.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=15.0,
    )
    max_distance = 25.0
    program = Program(
        project_id="test-evac-distance",
        num_floors=2,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=8)],
    )

    solution = solve(solar, program, max_distance_to_core_m=max_distance)
    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)

    for placement in solution.placements:
        ux = placement.bbox.x + placement.bbox.width / 2.0
        uy = placement.bbox.y + placement.bbox.height / 2.0
        best = min(
            abs(ux - (core.position.x + core.width_m / 2.0))
            + abs(uy - (core.position.y + core.depth_m / 2.0))
            for core in solution.communication_cores
        )
        assert best <= max_distance + 1e-6


def test_all_placements_contained_in_solar_polygon(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Cada bbox colocada debe quedar completamente dentro del polígono del solar.

    Verifica con Shapely que el solver no produce coordenadas fuera del contorno,
    más allá de la restricción de bbox que ya aplica el modelo CP-SAT.
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.geometry import box as shapely_box

    from cimiento.schemas import TypologyMix

    program = Program(
        project_id="test-spatial-containment",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=4)],
    )

    solution = solve(sample_solar_rectangular, program)
    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)

    solar_poly = ShapelyPolygon(
        [(p.x, p.y) for p in sample_solar_rectangular.contour.points]
    )
    for i, p in enumerate(solution.placements):
        unit_box = shapely_box(
            p.bbox.x, p.bbox.y,
            p.bbox.x + p.bbox.width, p.bbox.y + p.bbox.height,
        )
        assert solar_poly.covers(unit_box), (
            f"Unidad {i} en ({p.bbox.x:.2f},{p.bbox.y:.2f})–"
            f"({p.bbox.x + p.bbox.width:.2f},{p.bbox.y + p.bbox.height:.2f}) "
            "queda fuera del polígono del solar"
        )


def test_all_cores_contained_in_solar_polygon(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    La bbox de cada núcleo de comunicación debe quedar completamente dentro del solar.

    El solver aplica AddAllowedAssignments para los núcleos igual que para las unidades;
    este test verifica que las coordenadas finales son coherentes con ese confinamiento.
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.geometry import box as shapely_box

    from cimiento.schemas import TypologyMix

    program = Program(
        project_id="test-core-containment",
        num_floors=2,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=4)],
    )

    solution = solve(sample_solar_rectangular, program)
    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert solution.communication_cores, "Se esperaba al menos un núcleo"

    solar_poly = ShapelyPolygon(
        [(p.x, p.y) for p in sample_solar_rectangular.contour.points]
    )
    for i, core in enumerate(solution.communication_cores):
        core_box = shapely_box(
            core.position.x, core.position.y,
            core.position.x + core.width_m, core.position.y + core.depth_m,
        )
        assert solar_poly.covers(core_box), (
            f"Núcleo {i} en ({core.position.x:.2f},{core.position.y:.2f}) "
            "queda fuera del polígono del solar"
        )


def test_units_on_different_floors_may_share_xy_position(
    sample_typology_t2: Typology,
) -> None:
    """
    El solver aplica NoOverlap2D por planta, no entre plantas.

    Solar estrecho (8×11 m) que solo cabe 1 T2 por planta. Con 2 plantas y 2 unidades
    debe ser FEASIBLE porque las unidades de distintas plantas pueden compartir XY.
    Con 1 sola planta y 2 unidades, debe ser INFEASIBLE.
    """
    from cimiento.schemas import Point2D, Polygon2D, TypologyMix

    # 12×11 m: cabe exactamente 1 T2 (7×10) + 1 núcleo (4×6) sin solapamiento,
    # pero no caben 2 T2 en la misma planta (2×7=14 > 12 m de ancho).
    narrow_solar = Solar(
        id="solar-narrow-12x11",
        contour=Polygon2D(points=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=12.0, y=0.0),
            Point2D(x=12.0, y=11.0),
            Point2D(x=0.0, y=11.0),
        ]),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )

    program_2f = Program(
        project_id="test-floor-xy-2f",
        num_floors=2,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=2)],
    )
    solution_2f = solve(narrow_solar, program_2f)
    assert solution_2f.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE), (
        "Con 2 plantas distintas debe ser FEASIBLE aunque las unidades compartan XY"
    )
    assert solution_2f.metrics.num_units_placed == 2

    program_1f = Program(
        project_id="test-floor-xy-1f",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=2)],
    )
    solution_1f = solve(narrow_solar, program_1f)
    assert solution_1f.status == SolutionStatus.INFEASIBLE, (
        "Con 1 planta en solar estrecho, 2 T2 no caben → INFEASIBLE"
    )


def test_solver_mixed_typologies_all_placed(
    sample_solar_rectangular: Solar,
    sample_typology_t2: Typology,
) -> None:
    """
    Mezcla T1 (45 m²) + T2 (70 m²): todas las unidades de ambas tipologías deben colocarse
    y typology_fulfillment debe ser 1.0 para cada una.
    """
    from cimiento.schemas import Room, RoomType, TypologyMix

    typology_t1 = Typology(
        id="T1",
        name="Vivienda un dormitorio",
        min_useful_area=45.0,
        max_useful_area=60.0,
        num_bedrooms=1,
        num_bathrooms=1,
        rooms=[
            Room(type=RoomType.LIVING, min_area=15.0, min_short_side=3.0),
            Room(type=RoomType.KITCHEN, min_area=8.0, min_short_side=2.0),
            Room(type=RoomType.BEDROOM, min_area=10.0, min_short_side=2.5),
            Room(type=RoomType.BATHROOM, min_area=3.5, min_short_side=1.5),
        ],
    )

    program = Program(
        project_id="test-mixed-typologies",
        num_floors=2,
        floor_height_m=3.0,
        typologies=[typology_t1, sample_typology_t2],
        mix=[
            TypologyMix(typology_id="T1", count=3),
            TypologyMix(typology_id="T2", count=3),
        ],
    )

    solution = solve(sample_solar_rectangular, program)

    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert solution.metrics.num_units_placed == 6

    placed_t1 = sum(1 for p in solution.placements if p.typology_id == "T1")
    placed_t2 = sum(1 for p in solution.placements if p.typology_id == "T2")
    assert placed_t1 == 3, f"Se esperaban 3 T1, colocadas: {placed_t1}"
    assert placed_t2 == 3, f"Se esperaban 3 T2, colocadas: {placed_t2}"

    assert solution.metrics.typology_fulfillment["T1"] == pytest.approx(1.0)
    assert solution.metrics.typology_fulfillment["T2"] == pytest.approx(1.0)

    for i, a in enumerate(solution.placements):
        for b in solution.placements[i + 1:]:
            if a.floor == b.floor:
                assert not _rectangles_overlap(a.bbox, b.bbox), (
                    f"Solapamiento en planta {a.floor} entre unidades {i} y {i + 1}"
                )


def test_solver_l_shaped_solar_units_inside_polygon(
    sample_typology_t2: Typology,
) -> None:
    """
    Solar en L (20×30 con cuadrante [10–20]×[15–30] recortado):
    ninguna unidad puede colocarse en el área inexistente.

    Verifica con Shapely que cada placement queda dentro del polígono real,
    no solo dentro de la bbox del solar.
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.geometry import box as shapely_box

    from cimiento.schemas import Point2D, Polygon2D, TypologyMix

    l_solar = Solar(
        id="solar-l-shape-20x30",
        contour=Polygon2D(points=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=20.0, y=0.0),
            Point2D(x=20.0, y=15.0),
            Point2D(x=10.0, y=15.0),
            Point2D(x=10.0, y=30.0),
            Point2D(x=0.0, y=30.0),
        ]),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )

    program = Program(
        project_id="test-l-shape",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=3)],
    )

    solution = solve(l_solar, program)

    assert solution.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert solution.metrics.num_units_placed == 3

    solar_poly = ShapelyPolygon(
        [(p.x, p.y) for p in l_solar.contour.points]
    )
    for i, p in enumerate(solution.placements):
        unit_box = shapely_box(
            p.bbox.x, p.bbox.y,
            p.bbox.x + p.bbox.width, p.bbox.y + p.bbox.height,
        )
        assert solar_poly.covers(unit_box), (
            f"Unidad {i} en ({p.bbox.x:.2f},{p.bbox.y:.2f})–"
            f"({p.bbox.x + p.bbox.width:.2f},{p.bbox.y + p.bbox.height:.2f}) "
            "cae en el área recortada del solar en L"
        )
