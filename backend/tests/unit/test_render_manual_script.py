"""Tests del script manual de render para selección del binario de Blender."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import test_render_manual


def _make_args(tmp_path: Path, *, blender: str | None) -> SimpleNamespace:
    ifc = tmp_path / "model.ifc"
    ifc.write_text("stub")
    return SimpleNamespace(
        ifc=ifc,
        samples=1,
        device="AUTO",
        north_angle=0.0,
        blender=blender,
    )


def test_build_render_config_uses_settings_blender_executable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        test_render_manual,
        "settings",
        SimpleNamespace(blender_executable="/usr/local/bin/blender-official"),
    )

    config = test_render_manual._build_render_config(_make_args(tmp_path, blender=None))

    assert config.blender_executable == Path("/usr/local/bin/blender-official")


def test_build_render_config_prefers_cli_blender_executable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        test_render_manual,
        "settings",
        SimpleNamespace(blender_executable="/usr/bin/blender"),
    )

    config = test_render_manual._build_render_config(
        _make_args(tmp_path, blender="/opt/blender/current/blender")
    )

    assert config.blender_executable == Path("/opt/blender/current/blender")