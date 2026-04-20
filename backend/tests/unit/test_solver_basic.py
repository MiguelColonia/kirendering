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
    from cimiento.schemas import TypologyMix

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
