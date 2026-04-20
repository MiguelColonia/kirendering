"""
Script unificado de exportación: solver → builder → IFC + DXF + XLSX + SVG.

Dado un YAML de caso de solar, ejecuta el pipeline completo y reporta las rutas
de salida con tiempos de ejecución de cada etapa.

Uso:
    uv run python scripts/export_all.py data/solares_ejemplo/rectangular_simple.yaml
    uv run python scripts/export_all.py data/solares_ejemplo/rectangular_simple.yaml --timeout 30
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from cimiento.bim import export_to_dxf, export_to_ifc, export_to_xlsx, validate_ifc
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


def _load_case(yaml_path: Path) -> tuple[Solar, Program, dict]:
    data = yaml.safe_load(yaml_path.read_text())

    solar_data = data["solar"]
    pts = [Point2D(x=p["x"], y=p["y"]) for p in solar_data["contour"]]
    solar = Solar(
        id=solar_data["id"],
        contour=Polygon2D(points=pts),
        north_angle_deg=solar_data.get("north_angle_deg", 0.0),
        max_buildable_height_m=solar_data["max_buildable_height_m"],
    )

    prog_data = data["program"]
    typologies = []
    for t in prog_data["typologies"]:
        rooms = [
            Room(
                type=RoomType(r["type"]),
                min_area=r["min_area"],
                min_short_side=r["min_short_side"],
            )
            for r in t.get("rooms", [])
        ]
        typologies.append(
            Typology(
                id=t["id"],
                name=t["name"],
                min_useful_area=t["min_useful_area"],
                max_useful_area=t["max_useful_area"],
                num_bedrooms=t["num_bedrooms"],
                num_bathrooms=t["num_bathrooms"],
                rooms=rooms,
            )
        )
    mix = [TypologyMix(typology_id=m["typology_id"], count=m["count"]) for m in prog_data["mix"]]
    program = Program(
        project_id=prog_data["project_id"],
        num_floors=prog_data.get("num_floors", 1),
        floor_height_m=prog_data.get("floor_height_m", 3.0),
        typologies=typologies,
        mix=mix,
    )
    return solar, program, data.get("parking", {})


def _draw_svg(solar: Solar, solution, output_path: Path) -> None:
    """Genera un SVG sencillo del solar con las unidades colocadas."""
    pts = solar.contour.points
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = 10.0
    pad = 20
    w = (max_x - min_x) * scale + 2 * pad
    h = (max_y - min_y) * scale + 2 * pad

    def tx(x: float) -> float:
        return (x - min_x) * scale + pad

    def ty(y: float) -> float:
        return h - ((y - min_y) * scale + pad)

    solar_pts = " ".join(f"{tx(p.x)},{ty(p.y)}" for p in pts)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}">',
        f'<polygon points="{solar_pts}" fill="none" stroke="#333" stroke-width="2"/>',
    ]
    colors = ["#4A90D9", "#E67E22", "#27AE60", "#8E44AD", "#E74C3C",
              "#16A085", "#D35400", "#2980B9"]
    for i, p in enumerate(solution.placements):
        b = p.bbox
        c = colors[i % len(colors)]
        x = tx(b.x)
        y = ty(b.y + b.height)
        bw = b.width * scale
        bh = b.height * scale
        cx_ = tx(b.x + b.width / 2)
        cy_ = ty(b.y + b.height / 2)
        lines.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'fill="{c}" fill-opacity="0.5" stroke="{c}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{cx_:.1f}" y="{cy_:.1f}" font-size="8" text-anchor="middle" '
            f'fill="#333">{p.typology_id}</text>'
        )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run(yaml_path: Path, timeout: int) -> None:
    case_name = yaml_path.stem
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nCaso: {case_name}")
    print("-" * 60)

    # 1. Cargar caso
    solar, program, parking_cfg = _load_case(yaml_path)

    # 2. Solver
    t0 = time.perf_counter()
    solution = solve(solar, program, timeout_seconds=timeout)
    t_solver = time.perf_counter() - t0
    print(f"  Solver:  {solution.status} — {solution.metrics.num_units_placed} unidades "
          f"en {t_solver:.3f}s")

    parking_solution = None
    if parking_cfg.get("enabled", False):
        t0 = time.perf_counter()
        parking_solution = solve_parking(
            solar=solar,
            residential_solution=solution,
            floor_height_m=program.floor_height_m,
            parking_spaces_per_unit=parking_cfg.get("spaces_per_unit", 1.0),
            accessible_ratio=parking_cfg.get("accessible_ratio", 0.05),
            lane_width_m=parking_cfg.get("lane_width_m", 5.0),
            turning_radius_m=parking_cfg.get("turning_radius_m", 6.0),
            ramp_width_m=parking_cfg.get("ramp_width_m", 3.5),
            ramp_length_m=parking_cfg.get("ramp_length_m", 12.0),
            ramp_slope_pct=parking_cfg.get("ramp_slope_pct", 15.0),
        )
        t_parking = time.perf_counter() - t0
        print(
            f"  Parking: {parking_solution.status} — {parking_solution.metrics.total_spaces} plazas "
            f"en {t_parking:.3f}s"
        )
    else:
        t_parking = 0.0

    # 3. Builder
    t0 = time.perf_counter()
    building = build_building_from_solution(
        solar,
        program,
        solution,
        parking_solution=parking_solution,
    )
    t_builder = time.perf_counter() - t0
    print(f"  Builder: {t_builder:.3f}s")

    # 4. Exportaciones
    outputs = {}

    svg_path = out_dir / f"{case_name}.svg"
    t0 = time.perf_counter()
    _draw_svg(solar, solution, svg_path)
    outputs["SVG"] = (svg_path, time.perf_counter() - t0)

    ifc_path = out_dir / f"{case_name}.ifc"
    t0 = time.perf_counter()
    export_to_ifc(building, ifc_path)
    outputs["IFC"] = (ifc_path, time.perf_counter() - t0)

    dxf_path = out_dir / f"{case_name}.dxf"
    t0 = time.perf_counter()
    export_to_dxf(building, dxf_path)
    outputs["DXF"] = (dxf_path, time.perf_counter() - t0)

    xlsx_path = out_dir / f"{case_name}.xlsx"
    t0 = time.perf_counter()
    export_to_xlsx(building, program, xlsx_path)
    outputs["XLSX"] = (xlsx_path, time.perf_counter() - t0)

    print("\n  Archivos generados:")
    for fmt, (path, elapsed) in outputs.items():
        size_kb = path.stat().st_size / 1024
        print(f"    {fmt:<6} {str(path):<45} {size_kb:>7.1f} KB  {elapsed:.3f}s")

    # Validar IFC
    vr = validate_ifc(ifc_path)
    print(f"\n  Validación IFC: {'OK' if vr.valid else 'ERROR'} — "
          f"{vr.num_buildings} edificio(s), {vr.num_storeys} planta(s), "
          f"{vr.num_spaces} espacios, {vr.num_walls} muros, "
          f"{vr.num_doors} puertas")
    if vr.warnings:
        for w in vr.warnings:
            print(f"    ⚠  {w}")

    print(
        f"\n  Tiempo total: {t_solver + t_parking + t_builder + sum(t for _, t in outputs.values()):.3f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline completo: solver → IFC + DXF + XLSX")
    parser.add_argument("yaml", type=Path, help="Ruta al YAML del caso de solar")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout del solver en segundos")
    args = parser.parse_args()
    run(args.yaml, args.timeout)


if __name__ == "__main__":
    main()
