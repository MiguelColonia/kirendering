"""Tests unitarios del pipeline de difusión relacionados con selección de dispositivo."""

from __future__ import annotations

import sys
import types

import pytest

from cimiento.diffusion.pipeline import _detect_device


@pytest.mark.parametrize(
    ("hip_version", "cuda_available", "expected_device"),
    [
        ("5.7.1", True, "cuda"),
        (None, True, "cuda"),
        (None, False, "cpu"),
        ("5.7.1", False, "cpu"),
    ],
)
def test_detect_device_requires_available_gpu(
    monkeypatch: pytest.MonkeyPatch,
    hip_version: str | None,
    cuda_available: bool,
    expected_device: str,
) -> None:
    fake_torch = types.SimpleNamespace(
        version=types.SimpleNamespace(hip=hip_version),
        cuda=types.SimpleNamespace(is_available=lambda: cuda_available),
    )

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert _detect_device() == expected_device