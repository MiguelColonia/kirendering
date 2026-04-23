"""Tests del diagnóstico GPU de Blender."""

from __future__ import annotations

from scripts.check_blender_gpu import _parse_major_minor, _summarize


def test_parse_major_minor_accepts_semver_prefix() -> None:
    assert _parse_major_minor("5.7.1-3") == (5, 7)


def test_parse_major_minor_returns_none_for_missing_version() -> None:
    assert _parse_major_minor(None) is None
    assert _parse_major_minor("unknown") is None


def test_summarize_explains_rocm_runtime_mismatch_for_blender_51() -> None:
    exit_code, lines = _summarize(
        {
            "version": "5.1.1",
            "compute_device_types": [],
            "hip_runtime_version": "5.7.1-3",
        }
    )

    assert exit_code == 1
    assert any("ROCm HIP Runtime 6.0 o superior" in line for line in lines)


def test_summarize_keeps_generic_hint_without_runtime_info() -> None:
    exit_code, lines = _summarize(
        {
            "version": "4.0.2",
            "compute_device_types": [],
            "hip_runtime_version": None,
        }
    )

    assert exit_code == 1
    assert any("usar Blender oficial" in line for line in lines)