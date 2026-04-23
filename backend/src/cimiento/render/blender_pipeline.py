"""
Pipeline de render fotorrealista headless para Cimiento (capa Render, ADR 0014).

Flujo completo:
  IFC (canónico) → geometría OBJ (este módulo, vía ifcopenshell)
               → Blender Cycles headless (subprocess) → PNG(s)

Pipeline de render headless: IFC → OBJ (ifcopenshell) → Blender subprocess → PNG.

División de responsabilidades:
- Este módulo corre en el entorno Python del proyecto (con ifcopenshell).
- Extrae la geometría del IFC, la serializa como OBJ + JSON de escena.
- Lanza Blender en modo headless vía subprocess con blender_scripts/ifc_render.py.
- Recoge los PNGs generados y devuelve RenderResult.

Invariante: este módulo NUNCA importa bpy. Toda interacción con Blender es
vía subprocess. El script de Blender corre en el intérprete Python de Blender.
"""

from __future__ import annotations

import json
import logging
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom

from cimiento.schemas.render import RenderConfig, RenderResult, RenderView

logger = logging.getLogger(__name__)

# Directorio donde viven los scripts que ejecuta Blender
_SCRIPTS_DIR = Path(__file__).parent / "blender_scripts"

# Tipos IFC con geometría sólida visible; IfcSpace se omite deliberadamente
# porque es un volumen de referencia, no un elemento constructivo.
_RENDER_IFC_TYPES = (
    "IfcWallStandardCase",
    "IfcWall",
    "IfcSlab",
    "IfcDoor",
    "IfcWindow",
    "IfcColumn",
    "IfcBeam",
    "IfcRoof",
    "IfcStairFlight",
    "IfcRamp",
    "IfcPlate",
    "IfcMember",
)

# Materiales base disponibles para la escena Cycles
_MATERIAL_NAMES = {
    "mat_wall_exterior",
    "mat_wall_interior",
    "mat_slab_floor",
    "mat_slab_roof",
    "mat_door",
    "mat_window",
    "mat_column",
    "mat_generic",
}

# ---------------------------------------------------------------------------
# Helpers de clasificación IFC → material
# ---------------------------------------------------------------------------


def _ifc_product_to_material(product: Any) -> str:
    """Asigna un nombre de material OBJ a un producto IFC según clase y nombre."""
    cls = product.is_a()
    name = (product.Name or "").lower()

    if cls in ("IfcWallStandardCase", "IfcWall"):
        return "mat_wall_exterior" if "ext" in name else "mat_wall_interior"

    if cls == "IfcSlab":
        ptype = (product.PredefinedType or "").upper()
        return "mat_slab_roof" if ptype == "ROOF" else "mat_slab_floor"

    if cls == "IfcDoor":
        return "mat_door"

    if cls == "IfcWindow":
        return "mat_window"

    if cls in ("IfcColumn", "IfcBeam", "IfcMember", "IfcPlate"):
        return "mat_column"

    return "mat_generic"


# ---------------------------------------------------------------------------
# Extracción de geometría IFC → OBJ
# ---------------------------------------------------------------------------


def extract_geometry_to_obj(ifc_path: Path, obj_path: Path) -> dict[str, Any]:
    """
    Triangula todos los elementos visibles del IFC con ifcopenshell y escribe un OBJ.

    Devuelve el bounding box del modelo en coordenadas mundo:
    {"min": [x,y,z], "max": [x,y,z], "center": [x,y,z]}.

    El OBJ usa Z-up (igual que IFC y Blender) y grupos de material por tipo
    de elemento. La escala es metros.
    """
    ifc = ifcopenshell.open(str(ifc_path))

    geom_settings = ifcopenshell.geom.settings()
    geom_settings.set(geom_settings.USE_WORLD_COORDS, True)
    geom_settings.set(geom_settings.REORIENT_SHELLS, True)

    # mat_name → list of (verts_flat, faces_flat)
    groups: dict[str, list[tuple[tuple[float, ...], tuple[int, ...]]]] = {}

    all_xs: list[float] = []
    all_ys: list[float] = []
    all_zs: list[float] = []

    for ifc_type in _RENDER_IFC_TYPES:
        for product in ifc.by_type(ifc_type):
            if not product.Representation:
                continue
            try:
                shape = ifcopenshell.geom.create_shape(geom_settings, product)
            except Exception as exc:
                logger.debug("create_shape falló para %s %s: %s", ifc_type, product.GlobalId, exc)
                continue

            geo = shape.geometry
            verts = geo.verts  # (x0,y0,z0, x1,y1,z1, ...)
            faces = geo.faces  # (i0,i1,i2, i3,i4,i5, ...) triángulos

            if not verts or not faces:
                continue

            mat_name = _ifc_product_to_material(product)
            if mat_name not in groups:
                groups[mat_name] = []
            groups[mat_name].append((verts, faces))

            for i in range(0, len(verts), 3):
                all_xs.append(verts[i])
                all_ys.append(verts[i + 1])
                all_zs.append(verts[i + 2])

    _write_mtl(obj_path.with_suffix(".mtl"))
    _write_obj(obj_path, groups)

    if all_xs:
        bbox: dict[str, Any] = {
            "min": [min(all_xs), min(all_ys), min(all_zs)],
            "max": [max(all_xs), max(all_ys), max(all_zs)],
            "center": [
                (min(all_xs) + max(all_xs)) / 2.0,
                (min(all_ys) + max(all_ys)) / 2.0,
                (min(all_zs) + max(all_zs)) / 2.0,
            ],
        }
    else:
        logger.warning("No se extrajo geometría del IFC %s", ifc_path)
        bbox = {"min": [0.0, 0.0, 0.0], "max": [10.0, 10.0, 10.0], "center": [5.0, 5.0, 5.0]}

    return bbox


def _write_obj(obj_path: Path, groups: dict[str, list[tuple[Any, Any]]]) -> None:
    """Escribe el archivo OBJ con grupos de material y coordenadas Z-up."""
    mtl_name = obj_path.with_suffix(".mtl").name
    current_vertex_offset = 1  # OBJ usa índices base-1 globales

    with open(obj_path, "w", encoding="utf-8") as f:
        f.write(f"mtllib {mtl_name}\n")

        for mat_name, shapes in groups.items():
            f.write(f"\ng {mat_name}\nusemtl {mat_name}\n")

            for verts_flat, faces_flat in shapes:
                n_verts = len(verts_flat) // 3
                for i in range(n_verts):
                    x = verts_flat[i * 3]
                    y = verts_flat[i * 3 + 1]
                    z = verts_flat[i * 3 + 2]
                    f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")

                n_faces = len(faces_flat) // 3
                for i in range(n_faces):
                    i0 = faces_flat[i * 3] + current_vertex_offset
                    i1 = faces_flat[i * 3 + 1] + current_vertex_offset
                    i2 = faces_flat[i * 3 + 2] + current_vertex_offset
                    f.write(f"f {i0} {i1} {i2}\n")

                current_vertex_offset += n_verts


def _write_mtl(mtl_path: Path) -> None:
    """Escribe los materiales base en formato MTL (los Cycles los sobreescribe)."""
    definitions = {
        "mat_wall_exterior": (0.92, 0.90, 0.86),
        "mat_wall_interior": (0.96, 0.95, 0.93),
        "mat_slab_floor": (0.60, 0.58, 0.54),
        "mat_slab_roof": (0.68, 0.66, 0.62),
        "mat_door": (0.52, 0.38, 0.22),
        "mat_window": (0.60, 0.72, 0.85),
        "mat_column": (0.75, 0.73, 0.70),
        "mat_generic": (0.78, 0.78, 0.78),
    }
    with open(mtl_path, "w", encoding="utf-8") as f:
        for name, (r, g, b) in definitions.items():
            f.write(
                f"newmtl {name}\n"
                f"Ka {r:.3f} {g:.3f} {b:.3f}\n"
                f"Kd {r:.3f} {g:.3f} {b:.3f}\n"
                f"Ks 0.050 0.050 0.050\n"
                f"Ns 10.0\n\n"
            )


# ---------------------------------------------------------------------------
# Cálculo de cámaras
# ---------------------------------------------------------------------------


def compute_cameras(bbox: dict[str, Any], north_angle_deg: float) -> list[dict[str, Any]]:
    """
    Calcula las posiciones de 4-5 cámaras automáticas a partir del bounding box.

    Vistas generadas:
    - exterior_34: vista 3/4 exterior a ~225° respecto al norte (SO).
    - aerial: vista cenital a 1.2× diagonal sobre la cubierta.
    - interior_0 / interior_1: dos puntos de vista interiores a 1.6 m de altura.
    """
    bmin: list[float] = bbox["min"]
    bmax: list[float] = bbox["max"]
    cx: float = bbox["center"][0]
    cy: float = bbox["center"][1]

    dx = bmax[0] - bmin[0]
    dy = bmax[1] - bmin[1]
    dz = bmax[2] - bmin[2]
    diag = math.sqrt(dx * dx + dy * dy)

    # Exterior 3/4: posición al SO del edificio, mirando al centro de masa
    ext_angle = math.radians(north_angle_deg + 225.0)
    ext_dist = diag * 1.3
    ext_x = cx + ext_dist * math.sin(ext_angle)
    ext_y = cy + ext_dist * math.cos(ext_angle)
    ext_z = bmin[2] + dz * 0.8

    # Vista aérea: directamente encima, a 1.2× el diámetro del edificio
    aerial_z = bmax[2] + max(dx, dy) * 1.2

    # Puntos interiores a ±20 % del centro, altura 1.6 m
    floor_z = bmin[2] + 1.6
    int0_pos = [cx - dx * 0.20, cy - dy * 0.20, floor_z]
    int0_tgt = [cx + dx * 0.15, cy + dy * 0.10, floor_z]
    int1_pos = [cx + dx * 0.20, cy + dy * 0.20, floor_z]
    int1_tgt = [cx - dx * 0.10, cy - dy * 0.15, floor_z]

    return [
        {
            "name": "exterior_34",
            "position": [ext_x, ext_y, ext_z],
            "target": [cx, cy, bmin[2] + dz * 0.35],
            "lens_mm": 35,
        },
        {
            "name": "aerial",
            "position": [cx, cy, aerial_z],
            "target": [cx, cy, bmin[2]],
            "lens_mm": 28,
        },
        {
            "name": "interior_0",
            "position": int0_pos,
            "target": int0_tgt,
            "lens_mm": 20,
        },
        {
            "name": "interior_1",
            "position": int1_pos,
            "target": int1_tgt,
            "lens_mm": 20,
        },
    ]


# ---------------------------------------------------------------------------
# Invocación de Blender
# ---------------------------------------------------------------------------


def _find_blender(executable: Path) -> Path:
    """Resuelve el ejecutable de Blender; lanza RuntimeError si no lo encuentra."""
    import shutil

    candidate = shutil.which(str(executable))
    if candidate:
        return Path(candidate)
    if executable.exists():
        return executable
    raise RuntimeError(
        f"Blender no encontrado en '{executable}'. "
        "Instálalo con: sudo apt install blender  (v4.0 Ubuntu 24.04) "
        "o descarga el portable de https://www.blender.org/download/"
    )


def _parse_blender_version(stderr: str) -> str:
    """Extrae la versión de Blender del output de stderr."""
    match = re.search(r"Blender\s+([\d.]+)", stderr)
    return match.group(1) if match else "unknown"


def _parse_render_results(stdout: str, output_dir: Path) -> tuple[list[RenderView], str]:
    """
    Extrae las líneas RENDER_VIEW del stdout del script Blender.

    El script escribe una línea por cada vista renderizada:
    RENDER_VIEW name duration_s
    RENDER_DEVICE HIP|CPU
    """
    views: list[RenderView] = []
    device_used = "CPU"

    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("RENDER_VIEW "):
            parts = line.split()
            if len(parts) >= 3:
                name = parts[1]
                try:
                    duration = float(parts[2])
                except ValueError:
                    duration = 0.0
                png_path = output_dir / f"{name}.png"
                views.append(RenderView(name=name, output_path=png_path, duration_seconds=duration))
        elif line.startswith("RENDER_DEVICE "):
            parts = line.split()
            if len(parts) >= 2:
                device_used = parts[1]

    return views, device_used


def run_render(config: RenderConfig) -> RenderResult:
    """
    Ejecuta el pipeline completo de render para un IFC.

    1. Extrae geometría a OBJ en un directorio temporal.
    2. Calcula posiciones de cámara.
    3. Serializa la config de escena a JSON.
    4. Invoca Blender headless.
    5. Recoge los PNGs y devuelve RenderResult.
    """
    t_total_start = time.perf_counter()
    warnings: list[str] = []

    blender_bin = _find_blender(config.blender_executable)
    render_script = _SCRIPTS_DIR / "ifc_render.py"
    if not render_script.exists():
        raise FileNotFoundError(f"Script de Blender no encontrado: {render_script}")

    output_dir = config.output_dir / config.project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cimiento_render_") as tmp_str:
        tmp_dir = Path(tmp_str)
        obj_path = tmp_dir / "geometry.obj"
        scene_json_path = tmp_dir / "scene.json"

        # Paso 1: extraer geometría
        logger.info("Extrayendo geometría de %s", config.ifc_path)
        bbox = extract_geometry_to_obj(config.ifc_path, obj_path)

        # Paso 2: calcular cámaras
        cameras = compute_cameras(bbox, config.north_angle_deg)

        # Paso 3: serializar config de escena
        scene_cfg = {
            "obj_path": str(obj_path),
            "output_dir": str(output_dir),
            "north_angle_deg": config.north_angle_deg,
            "render_width": config.render_width,
            "render_height": config.render_height,
            "samples": config.samples,
            "device": str(config.device),
            "bounding_box": bbox,
            "cameras": cameras,
        }
        scene_json_path.write_text(json.dumps(scene_cfg, indent=2), encoding="utf-8")

        # Paso 4: invocar Blender
        cmd = [
            str(blender_bin),
            "--background",
            "--python",
            str(render_script),
            "--",
            "--config",
            str(scene_json_path),
        ]
        logger.info("Lanzando Blender: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Blender superó el timeout de {config.timeout_seconds}s. "
                "Aumenta RenderConfig.timeout_seconds o reduce samples."
            ) from exc

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined_output = f"{stdout}\n{stderr}"

        if result.returncode != 0:
            logger.error("Blender stderr:\n%s", stderr[-2000:])
            raise RuntimeError(
                f"Blender terminó con código {result.returncode}. Últimas líneas:\n{stderr[-800:]}"
            )

        if "Traceback (most recent call last):" in combined_output:
            logger.error("Blender reportó una excepción aunque devolvió código 0:\n%s", stderr)
            raise RuntimeError(
                "Blender ejecutó el script con errores internos. Últimas líneas:\n"
                f"{combined_output[-800:]}"
            )

        blender_version = _parse_blender_version(combined_output)
        views, device_used = _parse_render_results(stdout, output_dir)

        if not views:
            warnings.append(
                "Keine RENDER_VIEW-Zeilen in der Blender-Ausgabe gefunden. "
                "PNG-Dateien können vorhanden sein, Zeitangaben konnten jedoch nicht ermittelt werden."
            )
            # Intento de recuperación: listar PNGs generados
            for png in sorted(output_dir.glob("*.png")):
                views.append(RenderView(name=png.stem, output_path=png, duration_seconds=0.0))

    total_duration = time.perf_counter() - t_total_start

    return RenderResult(
        project_id=config.project_id,
        output_dir=output_dir,
        views=views,
        total_duration_seconds=round(total_duration, 2),
        device_used=device_used,
        blender_version=blender_version,
        warnings=warnings,
    )


__all__ = [
    "compute_cameras",
    "extract_geometry_to_obj",
    "run_render",
]
