"""
Visualiza la solución del solver para un solar y programa dados en YAML.

Uso:
    uv run python scripts/visualize_solution.py data/solares_ejemplo/rectangular_simple.yaml
    uv run python scripts/visualize_solution.py mi_caso.yaml --output data/outputs/resultado.svg
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

# Añadir src al path para importar cimiento sin instalar en modo editable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cimiento.schemas import Point2D, Program, Solar, Typology
from cimiento.schemas.typology import Room, RoomType
from cimiento.solver import solve

# Paleta de colores para tipologías (hasta 10 tipos distintos)
_PALETTE = [
    "#4A90D9",
    "#E67E22",
    "#27AE60",
    "#8E44AD",
    "#E74C3C",
    "#16A085",
    "#F39C12",
    "#2980B9",
    "#D35400",
    "#1ABC9C",
]

# Escala: píxeles por metro
_SCALE = 15
_MARGIN = 40
_LEGEND_WIDTH = 180


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _parse_solar(data: dict) -> Solar:
    return Solar(
        polygon=[Point2D(x=p["x"], y=p["y"]) for p in data["polygon"]],
        north_angle=data.get("north_angle", 0.0),
        max_height=data["max_height"],
    )


def _parse_typologies(data: dict) -> dict[str, Typology]:
    result = {}
    for typ_id, td in data.items():
        rooms = [
            Room(
                room_type=RoomType(r["room_type"]),
                min_area=r["min_area"],
                min_short_side=r["min_short_side"],
            )
            for r in td.get("required_rooms", [])
        ]
        result[typ_id] = Typology(
            id=td["id"],
            name=td["name"],
            min_area=td["min_area"],
            max_area=td["max_area"],
            bedrooms=td["bedrooms"],
            bathrooms=td["bathrooms"],
            required_rooms=rooms,
        )
    return result


def _parse_program(data: dict) -> Program:
    return Program(
        typology_mix={k: int(v) for k, v in data["typology_mix"].items()},
        total_buildable_area=data["total_buildable_area"],
        num_floors=data["num_floors"],
    )


def _solar_bounds(solar: Solar) -> tuple[float, float, float, float]:
    xs = [p.x for p in solar.polygon]
    ys = [p.y for p in solar.polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _m_to_px(value: float) -> float:
    return value * _SCALE


def _build_svg(solar: Solar, solution, typologies: dict[str, Typology]) -> ET.Element:
    min_x, min_y, max_x, max_y = _solar_bounds(solar)
    solar_w_m = max_x - min_x
    solar_h_m = max_y - min_y

    canvas_w = int(_m_to_px(solar_w_m) + 2 * _MARGIN + _LEGEND_WIDTH)
    canvas_h = int(_m_to_px(solar_h_m) + 2 * _MARGIN)

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(canvas_w),
            "height": str(canvas_h),
            "viewBox": f"0 0 {canvas_w} {canvas_h}",
            "font-family": "monospace",
            "font-size": "11",
        },
    )

    # Fondo blanco
    ET.SubElement(svg, "rect", {"width": str(canvas_w), "height": str(canvas_h), "fill": "white"})

    # Grupo principal (sistema de coordenadas: Y creciente hacia abajo en SVG)
    g = ET.SubElement(svg, "g")

    def to_svg_x(x: float) -> float:
        return _MARGIN + _m_to_px(x - min_x)

    def to_svg_y(y: float) -> float:
        # Invertir eje Y: en metros y=0 es abajo, en SVG y=0 es arriba
        return _MARGIN + _m_to_px(solar_h_m - (y - min_y))

    # Contorno del solar
    pts = " ".join(f"{to_svg_x(p.x):.1f},{to_svg_y(p.y):.1f}" for p in solar.polygon)
    ET.SubElement(
        g,
        "polygon",
        {
            "points": pts,
            "fill": "#F5F5F5",
            "stroke": "#000000",
            "stroke-width": "2",
        },
    )

    # Asignar color por tipología
    typ_ids = list(typologies.keys())
    color_map = {tid: _PALETTE[i % len(_PALETTE)] for i, tid in enumerate(typ_ids)}

    # Rectángulos de unidades
    for placement in solution.placements:
        bbox = placement.bbox
        color = color_map[placement.typology_id]

        rx = to_svg_x(bbox.x)
        ry = to_svg_y(bbox.y + bbox.height)  # esquina superior en SVG
        rw = _m_to_px(bbox.width)
        rh = _m_to_px(bbox.height)

        ET.SubElement(
            g,
            "rect",
            {
                "x": f"{rx:.1f}",
                "y": f"{ry:.1f}",
                "width": f"{rw:.1f}",
                "height": f"{rh:.1f}",
                "fill": color,
                "fill-opacity": "0.7",
                "stroke": "#333333",
                "stroke-width": "1",
            },
        )

        # Etiqueta centrada
        cx = rx + rw / 2
        cy = ry + rh / 2
        label = ET.SubElement(
            g,
            "text",
            {
                "x": f"{cx:.1f}",
                "y": f"{cy:.1f}",
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "fill": "#1A1A1A",
                "font-size": "10",
            },
        )
        label.text = placement.typology_id

    # Leyenda
    legend_x = _MARGIN + _m_to_px(solar_w_m) + 20
    legend_y = _MARGIN

    title = ET.SubElement(
        svg,
        "text",
        {
            "x": str(legend_x),
            "y": str(legend_y),
            "font-weight": "bold",
            "font-size": "12",
            "fill": "#111111",
        },
    )
    title.text = "Tipologías"

    for i, (tid, typology) in enumerate(typologies.items()):
        row_y = legend_y + 20 + i * 22
        color = color_map[tid]
        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(legend_x),
                "y": str(row_y - 10),
                "width": "14",
                "height": "14",
                "fill": color,
                "fill-opacity": "0.7",
                "stroke": "#333",
                "stroke-width": "1",
            },
        )
        count = solution.metrics.units_placed // len(typologies) if typologies else 0
        count = sum(1 for p in solution.placements if p.typology_id == tid)
        label = ET.SubElement(
            svg,
            "text",
            {
                "x": str(legend_x + 20),
                "y": str(row_y + 2),
                "fill": "#222222",
            },
        )
        label.text = f"{tid} — {typology.name} ({count} ud.)"

    # Métricas resumidas
    metrics_y = legend_y + 20 + len(typologies) * 22 + 20
    for line in [
        f"Estado: {solution.status}",
        f"Unidades: {solution.metrics.units_placed}",
        f"Área total: {solution.metrics.total_area:.0f} m²",
        f"Cumplimiento: {solution.metrics.compliance_ratio:.0%}",
    ]:
        t = ET.SubElement(
            svg,
            "text",
            {"x": str(legend_x), "y": str(metrics_y), "fill": "#444444", "font-size": "10"},
        )
        t.text = line
        metrics_y += 16

    return svg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta el solver y genera un SVG de la distribución de viviendas."
    )
    parser.add_argument("input", type=Path, help="Ruta al YAML con solar, tipologías y programa")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta de salida del SVG (por defecto data/outputs/<stem>.svg)",
    )
    parser.add_argument(
        "--grid-size",
        type=float,
        default=0.5,
        help="Resolución de la rejilla en metros (por defecto 0.5)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout del solver en segundos (por defecto 60)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: no existe el archivo '{args.input}'", file=sys.stderr)
        sys.exit(1)

    data = _load_yaml(args.input)
    solar = _parse_solar(data["solar"])
    typologies = _parse_typologies(data["typologies"])
    program = _parse_program(data["program"])

    print(f"Ejecutando solver (grid={args.grid_size}m, timeout={args.timeout}s)…")
    solution = solve(solar, program, typologies, grid_size=args.grid_size, timeout_s=args.timeout)
    print(f"  Estado: {solution.status}")
    print(f"  Unidades colocadas: {solution.metrics.units_placed}")
    print(f"  Área total: {solution.metrics.total_area:.1f} m²")
    print(f"  Cumplimiento: {solution.metrics.compliance_ratio:.0%}")

    if args.output is None:
        output_dir = Path(__file__).parent.parent.parent / "data" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = output_dir / f"{args.input.stem}.svg"

    svg = _build_svg(solar, solution, typologies)
    tree = ET.ElementTree(svg)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="unicode", xml_declaration=False)
    print(f"SVG guardado en: {args.output}")


if __name__ == "__main__":
    main()
