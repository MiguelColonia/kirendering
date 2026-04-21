"""
Script de render para Blender headless — corre en el intérprete Python de Blender.

Uso (llamado por blender_pipeline.py vía subprocess):
    blender --background --python ifc_render.py -- --config /path/to/scene.json

Este script NO puede importar módulos del proyecto (cimiento.*). Toda la
información llega en el JSON de escena. Escribe por stdout líneas con prefijo
RENDER_VIEW y RENDER_DEVICE que el pipeline lee para construir RenderResult.

Blender 4.0 requiere. OBJ importado con up_axis='Z' para respetar coordenadas
IFC (Z-arriba). Materiales Principled BSDF con Cycles. Sky Texture Nishita
(sin HDRI externo). GPU: HIP para RX 6600, CPU como fallback.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Euler, Vector

# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    idx = sys.argv.index("--") if "--" in sys.argv else len(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Ruta al JSON de configuración de escena")
    return parser.parse_args(sys.argv[idx + 1:])


# ---------------------------------------------------------------------------
# Escena base
# ---------------------------------------------------------------------------

def clear_scene() -> None:
    """Elimina todos los objetos de la escena por defecto."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.cameras):
        bpy.data.cameras.remove(block, do_unlink=True)
    for block in list(bpy.data.lights):
        bpy.data.lights.remove(block, do_unlink=True)


# ---------------------------------------------------------------------------
# Importación del OBJ
# ---------------------------------------------------------------------------

def import_obj(obj_path: str) -> None:
    """Importa el OBJ con coordenadas Z-up (igual que IFC)."""
    bpy.ops.wm.obj_import(
        filepath=obj_path,
        forward_axis="Y",
        up_axis="Z",
    )
    # Recalcula normales hacia el exterior en todos los objetos importados
    for obj in bpy.context.selected_objects:
        if obj.type != "MESH":
            continue
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")


# ---------------------------------------------------------------------------
# Materiales Cycles
# ---------------------------------------------------------------------------

# Definición de materiales: color RGBA, roughness, metallic, transmission
_MATERIAL_DEFS: dict[str, dict] = {
    "mat_wall_exterior": {
        "color": (0.92, 0.90, 0.86, 1.0),
        "roughness": 0.75,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_wall_interior": {
        "color": (0.96, 0.95, 0.93, 1.0),
        "roughness": 0.85,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_slab_floor": {
        "color": (0.60, 0.58, 0.54, 1.0),
        "roughness": 0.90,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_slab_roof": {
        "color": (0.68, 0.66, 0.62, 1.0),
        "roughness": 0.88,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_door": {
        "color": (0.52, 0.38, 0.22, 1.0),
        "roughness": 0.40,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_window": {
        "color": (0.60, 0.72, 0.85, 1.0),
        "roughness": 0.0,
        "metallic": 0.0,
        "transmission": 0.85,
        "ior": 1.45,
    },
    "mat_column": {
        "color": (0.75, 0.73, 0.70, 1.0),
        "roughness": 0.80,
        "metallic": 0.0,
        "transmission": 0.0,
    },
    "mat_generic": {
        "color": (0.78, 0.78, 0.78, 1.0),
        "roughness": 0.70,
        "metallic": 0.0,
        "transmission": 0.0,
    },
}


def _setup_principled(mat: bpy.types.Material, defn: dict) -> None:
    """Sustituye los nodos del material por Principled BSDF Cycles."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    output = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    output.location = (400, 0)
    bsdf.location = (0, 0)

    bsdf.inputs["Base Color"].default_value = defn["color"]
    bsdf.inputs["Roughness"].default_value = defn["roughness"]
    bsdf.inputs["Metallic"].default_value = defn["metallic"]

    # Blender 4.0: el input de transmisión es "Transmission Weight"
    if defn.get("transmission", 0.0) > 0.0:
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = defn["transmission"]
        elif "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = defn["transmission"]
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = defn.get("ior", 1.45)
        mat.blend_method = "BLEND"


def apply_materials() -> None:
    """Aplica o crea materiales Cycles en todos los objetos importados."""
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            mat_name = slot.material.name
            defn = _MATERIAL_DEFS.get(mat_name, _MATERIAL_DEFS["mat_generic"])
            _setup_principled(slot.material, defn)


# ---------------------------------------------------------------------------
# Iluminación: Sky Texture Nishita + luz solar
# ---------------------------------------------------------------------------

def setup_lighting(north_angle_deg: float) -> None:
    """
    Configura un cielo procedural Nishita con sol orientado según el norte.

    north_angle_deg es el ángulo del norte en el sistema del Solar (desde Y+
    en sentido antihorario). En Blender, la rotación del sol en la Sky Texture
    es azimut desde +Y en sentido horario, así que negamos el signo.
    """
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    output = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(42.0)   # ~sol de media mañana
    sky.sun_rotation = math.radians(-north_angle_deg)
    sky.altitude = 100.0
    sky.air_density = 1.0
    sky.dust_density = 0.5

    bg.inputs["Strength"].default_value = 1.2
    output.location = (600, 0)
    bg.location = (300, 0)
    sky.location = (0, 0)

    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], output.inputs["Surface"])

    # Luz solar explícita para sombras nítidas
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 0))
    sun = bpy.context.active_object
    sun.name = "SunLight"
    sun.data.energy = 5.0
    sun.data.angle = math.radians(0.5)  # disco solar real ≈ 0.5°
    # Orientación: elevación 42°, azimut según north_angle
    sun_azimuth_rad = math.radians(north_angle_deg + 180.0)
    sun.rotation_euler = Euler((
        math.radians(90.0 - 42.0),
        0.0,
        sun_azimuth_rad,
    ), "XYZ")


# ---------------------------------------------------------------------------
# Cámaras
# ---------------------------------------------------------------------------

def _look_at(cam_obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    """Apunta la cámara hacia target (usando -Z como eje de visión, Y arriba)."""
    pos = cam_obj.location
    direction = Vector(target) - pos
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()


def setup_cameras(cameras_data: list[dict]) -> list[bpy.types.Object]:
    """Crea las cámaras definidas en la config de escena y devuelve sus objetos."""
    cam_objects: list[bpy.types.Object] = []

    for cam_def in cameras_data:
        name: str = cam_def["name"]
        pos: list[float] = cam_def["position"]
        tgt: list[float] = cam_def["target"]
        lens: float = cam_def.get("lens_mm", 35.0)

        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = lens
        cam_data.clip_start = 0.1
        cam_data.clip_end = 1000.0

        cam_obj = bpy.data.objects.new(name, cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = Vector(pos)
        _look_at(cam_obj, tuple(tgt))

        cam_objects.append(cam_obj)

    return cam_objects


# ---------------------------------------------------------------------------
# Configuración de render Cycles
# ---------------------------------------------------------------------------

def detect_gpu(preferred: str) -> str:
    """
    Intenta activar HIP (RX 6600) para Cycles. Devuelve 'HIP' o 'CPU'.

    En Blender 4.0 los addons de Cycles siguen disponibles en
    bpy.context.preferences.addons['cycles'].preferences.
    """
    if preferred == "CPU":
        bpy.context.scene.cycles.device = "CPU"
        return "CPU"

    try:
        cycles_addon = bpy.context.preferences.addons.get("cycles")
        if cycles_addon is None:
            raise RuntimeError("addon cycles no disponible")

        cprefs = cycles_addon.preferences
        cprefs.compute_device_type = "HIP"
        cprefs.get_devices()

        hip_devices = [d for d in cprefs.devices if d.type == "HIP"]
        if hip_devices:
            for dev in cprefs.devices:
                dev.use = dev.type == "HIP"
            bpy.context.scene.cycles.device = "GPU"
            return "HIP"

        # Intentar CUDA como segunda opción
        cprefs.compute_device_type = "CUDA"
        cprefs.get_devices()
        cuda_devices = [d for d in cprefs.devices if d.type == "CUDA"]
        if cuda_devices:
            for dev in cprefs.devices:
                dev.use = dev.type == "CUDA"
            bpy.context.scene.cycles.device = "GPU"
            return "CUDA"

    except Exception as exc:
        print(f"GPU detection warning: {exc}", file=sys.stderr)

    bpy.context.scene.cycles.device = "CPU"
    return "CPU"


def setup_render_settings(cfg: dict, device_used: str) -> None:
    """Configura el motor Cycles y los parámetros de imagen."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = cfg["render_width"]
    scene.render.resolution_y = cfg["render_height"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"

    scene.cycles.samples = cfg["samples"]
    scene.cycles.use_denoising = True
    # Denoiser: OPENIMAGEDENOISE es CPU, OptiX es NVIDIA — usar OPENIMAGEDENOISE seguro
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.preview_samples = 0


# ---------------------------------------------------------------------------
# Loop de render por cámara
# ---------------------------------------------------------------------------

def render_views(
    cam_objects: list[bpy.types.Object],
    output_dir: str,
) -> None:
    """
    Renderiza cada cámara y guarda el PNG. Imprime RENDER_VIEW por stdout.
    """
    scene = bpy.context.scene
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for cam_obj in cam_objects:
        scene.camera = cam_obj
        png_path = out / f"{cam_obj.name}.png"
        scene.render.filepath = str(png_path)

        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        duration = round(time.perf_counter() - t0, 2)

        # El pipeline lee estas líneas para construir RenderResult
        print(f"RENDER_VIEW {cam_obj.name} {duration}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config no encontrado: {config_path}", file=sys.stderr)
        sys.exit(1)

    cfg: dict = json.loads(config_path.read_text(encoding="utf-8"))

    print("Limpiando escena...", flush=True)
    clear_scene()

    print(f"Importando OBJ: {cfg['obj_path']}", flush=True)
    import_obj(cfg["obj_path"])

    print("Aplicando materiales Cycles...", flush=True)
    apply_materials()

    print("Configurando iluminación...", flush=True)
    setup_lighting(cfg.get("north_angle_deg", 0.0))

    print("Configurando cámaras...", flush=True)
    cam_objects = setup_cameras(cfg.get("cameras", []))

    if not cam_objects:
        print("ERROR: no hay cámaras definidas en la configuración.", file=sys.stderr)
        sys.exit(1)

    device_used = detect_gpu(cfg.get("device", "AUTO"))
    print(f"RENDER_DEVICE {device_used}", flush=True)
    print(f"Dispositivo Cycles: {device_used}", flush=True)

    setup_render_settings(cfg, device_used)

    print(f"Renderizando {len(cam_objects)} vista(s)...", flush=True)
    render_views(cam_objects, cfg["output_dir"])

    print("Render completado.", flush=True)


if __name__ == "__main__":
    main()
