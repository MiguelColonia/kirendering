"""
Test manual del pipeline de render — Fase 8.

Prerrequisito: Blender 4.0 instalado.
    sudo apt install blender        # Ubuntu 24.04
    # o descarga portable de https://www.blender.org/download/

Uso:
    cd backend
    uv run python scripts/test_render_manual.py [--ifc PATH] [--samples N] [--device AUTO|HIP|CPU]

El script mide el tiempo de cada vista y muestra el resumen por consola.
Los PNGs se guardan en data/outputs/renders/test_render_manual/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Asegurar que el módulo cimiento es importable desde scripts/
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from cimiento.render.blender_pipeline import run_render
from cimiento.schemas.render import RenderConfig, RenderDevice

_DEFAULT_IFC = (
    Path(__file__).parents[1] / "data" / "outputs" / "rectangular_simple.ifc"
)
_DEFAULT_OUT = (
    Path(__file__).parents[1] / "data" / "outputs" / "renders"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test manual render pipeline Fase 8")
    parser.add_argument("--ifc", type=Path, default=_DEFAULT_IFC, help="Ruta al IFC")
    parser.add_argument("--samples", type=int, default=64, help="Muestras Cycles")
    parser.add_argument(
        "--device",
        choices=["AUTO", "HIP", "CPU"],
        default="AUTO",
        help="Dispositivo Cycles",
    )
    parser.add_argument("--north-angle", type=float, default=0.0, help="Ángulo norte grados")
    args = parser.parse_args()

    if not args.ifc.exists():
        print(f"ERROR: IFC no encontrado: {args.ifc}")
        sys.exit(1)

    print("=" * 60)
    print("Cimiento — Test manual render Fase 8")
    print("=" * 60)
    print(f"  IFC:       {args.ifc}")
    print(f"  Samples:   {args.samples}")
    print(f"  Device:    {args.device}")
    print(f"  Norte:     {args.north_angle}°")
    print()

    config = RenderConfig(
        ifc_path=args.ifc,
        project_id="test_render_manual",
        output_dir=_DEFAULT_OUT,
        north_angle_deg=args.north_angle,
        samples=args.samples,
        device=RenderDevice(args.device),
        render_width=2048,
        render_height=1152,
    )

    try:
        result = run_render(config)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"Blender {result.blender_version}  |  Dispositivo: {result.device_used}")
    print(f"Tiempo total: {result.total_duration_seconds:.1f}s")
    print()

    if result.views:
        print(f"{'Vista':<20} {'Tiempo (s)':>10}  {'PNG'}")
        print("-" * 60)
        for view in result.views:
            exists = "✓" if view.output_path.exists() else "✗ NO ENCONTRADO"
            print(f"{view.name:<20} {view.duration_seconds:>10.1f}  {exists}")
        print()
        print(f"PNGs en: {result.output_dir}")
    else:
        print("No se generaron vistas.")

    if result.warnings:
        print("\nAdvertencias:")
        for w in result.warnings:
            print(f"  ! {w}")

    print()


if __name__ == "__main__":
    main()
