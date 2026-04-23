"""Diagnóstico de soporte GPU de Blender/Cycles en el host actual.

Uso:
    cd backend
    uv run python scripts/check_blender_gpu.py [--blender /ruta/a/blender]

El script distingue entre tres estados habituales:
1. Blender sin backend HIP/CUDA compilado o expuesto.
2. Blender con backend HIP expuesto, pero sin dispositivos detectados.
3. Blender con backend HIP y dispositivo usable.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _resolve_blender(executable: str) -> Path:
    candidate = shutil.which(executable)
    if candidate:
        return Path(candidate)

    path = Path(executable)
    if path.exists():
        return path.resolve()

    raise RuntimeError(f"Blender no encontrado: {executable}")


def _parse_major_minor(version: str | None) -> tuple[int, int] | None:
    if not version:
        return None

    match = re.search(r"(\d+)\.(\d+)", version)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def _detect_hip_runtime_version() -> str | None:
    commands = [
        ["hipconfig", "--version"],
        ["dpkg-query", "-W", "-f=${Version}", "libamdhip64-6"],
        ["dpkg-query", "-W", "-f=${Version}", "libamdhip64-5"],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:  # noqa: BLE001
            continue

        if result.returncode != 0:
            continue

        text = (result.stdout or "").strip()
        if not text:
            continue

        if cmd[:2] == ["hipconfig", "--version"]:
            match = re.search(r"HIP version:\s*([\d.]+)", text)
            if match:
                return match.group(1)
            continue

        return text

    return None


def _probe_script() -> str:
    return (
        "import bpy, json\n"
        "payload = {'version': bpy.app.version_string}\n"
        "try:\n"
        "    cprefs = bpy.context.preferences.addons['cycles'].preferences\n"
        "    prop = cprefs.bl_rna.properties['compute_device_type']\n"
        "    payload['compute_device_types'] = [item.identifier for item in prop.enum_items]\n"
        "    payload['current_compute_device_type'] = cprefs.compute_device_type\n"
        "    payload['devices'] = {}\n"
        "    for device_type in payload['compute_device_types']:\n"
        "        try:\n"
        "            cprefs.compute_device_type = device_type\n"
        "            cprefs.get_devices()\n"
        "            payload['devices'][device_type] = [\n"
        "                {'name': getattr(d, 'name', '?'), 'type': getattr(d, 'type', '?'), 'use': bool(getattr(d, 'use', False))}\n"
        "                for d in cprefs.devices\n"
        "            ]\n"
        "        except Exception as exc:\n"
        "            payload['devices'][device_type] = {'error': str(exc)}\n"
        "except Exception as exc:\n"
        "    payload['error'] = str(exc)\n"
        "print('BLENDER_GPU_PROBE ' + json.dumps(payload))\n"
    )


def _run_probe(blender_bin: Path) -> dict[str, Any]:
    cmd = [
        str(blender_bin),
        "--background",
        "--python-expr",
        _probe_script(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(
            f"Blender terminó con código {result.returncode}.\n{(result.stderr or result.stdout)[-800:]}"
        )

    for line in result.stdout.splitlines():
        if line.startswith("BLENDER_GPU_PROBE "):
            return json.loads(line.split(" ", 1)[1])

    raise RuntimeError(
        "No se pudo extraer el resultado del probe de Blender.\n"
        f"Stdout:\n{result.stdout[-1200:]}\nStderr:\n{result.stderr[-1200:]}"
    )


def _summarize(probe: dict[str, Any]) -> tuple[int, list[str]]:
    lines = [f"Blender: {probe.get('version', 'unknown')}"]
    compute_types = probe.get("compute_device_types", [])
    lines.append(f"Cycles compute_device_type: {compute_types or '[]'}")

    hip_runtime_version = probe.get("hip_runtime_version")
    if hip_runtime_version:
        lines.append(f"ROCm HIP runtime: {hip_runtime_version}")

    if probe.get("error"):
        lines.append(f"ERROR probe Cycles: {probe['error']}")
        return 2, lines

    if not compute_types:
        blender_version = _parse_major_minor(probe.get("version"))
        hip_runtime = _parse_major_minor(hip_runtime_version)

        lines.append("Diagnóstico: Blender no expone backends GPU en Cycles.")
        if blender_version is not None and blender_version >= (5, 1) and hip_runtime is not None and hip_runtime < (6, 0):
            lines.append(
                "Causa probable: Blender 5.1 en Linux requiere ROCm HIP Runtime 6.0 o superior, y el host parece usar una versión anterior."
            )
            lines.append(
                "Acción recomendada: actualizar ROCm/HIP Runtime a 6.0+ antes de esperar soporte HIP en Cycles."
            )
        else:
            lines.append(
                "Acción recomendada: usar Blender oficial de blender.org en lugar del paquete Ubuntu/Debian si se necesita HIP."
            )
        return 1, lines

    devices = probe.get("devices", {})
    for device_type in compute_types:
        lines.append(f"{device_type}: {devices.get(device_type, [])}")

    hip_devices = devices.get("HIP", []) if isinstance(devices.get("HIP", []), list) else []
    hip_gpu_devices = [device for device in hip_devices if device.get("type") == "HIP"]

    if "HIP" not in compute_types:
        lines.append("Diagnóstico: Blender no fue compilado con backend HIP visible.")
        lines.append(
            "Acción recomendada: instalar Blender oficial con soporte HIP o validar otra versión/build."
        )
        return 1, lines

    if not hip_gpu_devices:
        lines.append(
            "Diagnóstico: Blender expone HIP, pero no detecta ninguna GPU HIP usable en Cycles."
        )
        lines.append(
            "Acción recomendada: revisar ROCm, permisos/grupos y compatibilidad de la build de Blender con HIP."
        )
        return 1, lines

    enabled = [device for device in hip_gpu_devices if device.get("use")]
    lines.append(f"Dispositivos HIP detectados: {hip_gpu_devices}")
    lines.append(
        "Diagnóstico: Blender detecta HIP correctamente."
        if hip_gpu_devices
        else "Diagnóstico: sin dispositivo HIP usable."
    )
    if enabled:
        lines.append(f"Dispositivos HIP marcados para uso: {enabled}")
    return 0, lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico GPU de Blender/Cycles")
    parser.add_argument("--blender", default="blender", help="Ruta o nombre del ejecutable de Blender")
    args = parser.parse_args()

    try:
        blender_bin = _resolve_blender(args.blender)
        probe = _run_probe(blender_bin)
        probe["hip_runtime_version"] = _detect_hip_runtime_version()
        exit_code, lines = _summarize(probe)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        return 2

    for line in lines:
        print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())