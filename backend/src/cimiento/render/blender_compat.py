"""Compatibilidad entre versiones de Blender usadas por el pipeline de render."""

from __future__ import annotations

from collections.abc import Iterable


def choose_sky_type(available_types: Iterable[str]) -> str:
    """Elige el sky_type más compatible posible según la versión de Blender."""
    available = set(available_types)
    preferred_order = (
        "NISHITA",
        "MULTIPLE_SCATTERING",
        "SINGLE_SCATTERING",
        "PREETHAM",
        "HOSEK_WILKIE",
    )

    for sky_type in preferred_order:
        if sky_type in available:
            return sky_type

    raise ValueError(f"No hay sky_type compatible en Blender: {sorted(available)}")


def choose_sky_haze_property(available_properties: Iterable[str]) -> str | None:
    """Devuelve la propiedad equivalente de densidad atmosférica según la versión."""
    available = set(available_properties)

    if "dust_density" in available:
        return "dust_density"
    if "aerosol_density" in available:
        return "aerosol_density"
    return None