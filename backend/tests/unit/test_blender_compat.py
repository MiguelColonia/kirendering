"""Tests de compatibilidad entre APIs de Blender soportadas por Cimiento."""

from __future__ import annotations

import pytest

from cimiento.render.blender_compat import choose_sky_haze_property, choose_sky_type


def test_choose_sky_type_prefers_nishita_when_available() -> None:
    assert choose_sky_type(["PREETHAM", "NISHITA", "HOSEK_WILKIE"]) == "NISHITA"


def test_choose_sky_type_falls_back_to_multiple_scattering() -> None:
    assert choose_sky_type(["MULTIPLE_SCATTERING", "PREETHAM"]) == "MULTIPLE_SCATTERING"


def test_choose_sky_type_falls_back_to_single_scattering() -> None:
    assert choose_sky_type(["SINGLE_SCATTERING", "PREETHAM"]) == "SINGLE_SCATTERING"


def test_choose_sky_type_raises_when_no_supported_option_exists() -> None:
    with pytest.raises(ValueError, match="No hay sky_type compatible"):
        choose_sky_type([])


def test_choose_sky_haze_property_prefers_legacy_dust_density() -> None:
    assert choose_sky_haze_property(["dust_density", "air_density"]) == "dust_density"


def test_choose_sky_haze_property_falls_back_to_aerosol_density() -> None:
    assert choose_sky_haze_property(["aerosol_density", "air_density"]) == "aerosol_density"


def test_choose_sky_haze_property_returns_none_when_missing() -> None:
    assert choose_sky_haze_property(["air_density", "altitude"]) is None