"""
Benchmark del solver de distribución espacial.

Ejecuta el solver en tres casos de referencia y muestra una tabla con
el status, el número de unidades colocadas y el tiempo de resolución.
No es un test: no hay asserts. Es una herramienta de diagnóstico.

Uso:
    uv run python scripts/benchmark_solver.py
    uv run python scripts/benchmark_solver.py --timeout 120
"""

import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cimiento.bim import export_to_ifc
from cimiento.geometry import build_building_from_solution
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
from cimiento.solver import solve, solve_parking


def _typology_t2() -> Typology:
    return Typology(
        id="T2",
        name="Vivienda dos dormitorios",
        min_useful_area=70.0,
        max_useful_area=90.0,
        num_bedrooms=2,
        num_bathrooms=1,
        rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5)],
    )


def _solar(width_m: float, height_m: float, label: str) -> Solar:
    return Solar(
        id=label,
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=width_m, y=0.0),
                Point2D(x=width_m, y=height_m),
                Point2D(x=0.0, y=height_m),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )


def _program(t2: Typology, count: int, num_floors: int) -> Program:
    return Program(
        project_id=f"benchmark-{count}T2-{num_floors}f",
        num_floors=num_floors,
        floor_height_m=3.0,
        typologies=[t2],
        mix=[TypologyMix(typology_id="T2", count=count)],
    )


CASES = [
    ("12 T2 · 3 plantas · solar 40×40 m", 40.0, 40.0, 12, 3, False),
    ("40 T2 · 4 plantas · solar 60×80 m", 60.0, 80.0, 40, 4, False),
    ("60 T2 · 8 plantas · parking · solar 90×90 m", 90.0, 90.0, 60, 8, True),
]


def run_benchmark(timeout: int) -> None:
    t2 = _typology_t2()

    header = (
        f"{'Caso':<44} {'Status':<12} {'Unids':>5} {'Nuc':>4} {'Pk':>4} "
        f"{'Solver':>8} {'Parking':>8} {'Builder':>8} {'IFC':>7} {'Total':>8}"
    )
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)

    for label, w, h, count, num_floors, with_parking in CASES:
        solar = _solar(w, h, label)
        program = _program(t2, count, num_floors)

        t0 = time.perf_counter()
        solution = solve(solar, program, timeout_seconds=timeout)
        t_solver = time.perf_counter() - t0

        parking_solution = None
        t_parking = 0.0
        if with_parking:
            t0 = time.perf_counter()
            parking_solution = solve_parking(
                solar=solar,
                residential_solution=solution,
                floor_height_m=program.floor_height_m,
            )
            t_parking = time.perf_counter() - t0

        t0 = time.perf_counter()
        building = build_building_from_solution(
            solar,
            program,
            solution,
            parking_solution=parking_solution,
        )
        t_builder = time.perf_counter() - t0

        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=True) as f:
            ifc_path = Path(f.name)
        t0 = time.perf_counter()
        export_to_ifc(building, ifc_path)
        t_ifc = time.perf_counter() - t0
        if ifc_path.exists():
            ifc_path.unlink()

        total = t_solver + t_parking + t_builder + t_ifc
        print(
            f"{label:<44} {solution.status:<12} {solution.metrics.num_units_placed:>5} "
            f"{len(solution.communication_cores):>4} "
            f"{parking_solution.metrics.total_spaces if parking_solution else 0:>4} "
            f"{t_solver:>7.3f}s {t_parking:>7.3f}s {t_builder:>7.3f}s {t_ifc:>6.3f}s {total:>7.3f}s"
        )

    print(separator)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark del solver CP-SAT de Cimiento.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout por caso en segundos (por defecto 60)",
    )
    args = parser.parse_args()
    run_benchmark(args.timeout)


if __name__ == "__main__":
    main()
