"""
Tests unitarios para la capa de render.

No requieren Blender instalado: verifican la extracción de geometría,
el cálculo de cámaras y la validación de schemas.
El test de integración completo (que lanza Blender) está en
backend/scripts/test_render_manual.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cimiento.render.blender_pipeline import (
    _ifc_product_to_material,
    _parse_render_results,
    compute_cameras,
    extract_geometry_to_obj,
)
from cimiento.schemas.render import RenderConfig, RenderDevice, RenderResult, RenderView

# IFC de referencia del proyecto (el caso ejemplo)
_EXAMPLE_IFC = Path(__file__).parents[2] / "data" / "outputs" / "rectangular_simple.ifc"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestRenderConfig:
    def test_default_device_is_auto(self, tmp_path: Path) -> None:
        ifc = tmp_path / "model.ifc"
        ifc.write_text("stub")
        cfg = RenderConfig(ifc_path=ifc, project_id="p1", output_dir=tmp_path)
        assert cfg.device == RenderDevice.AUTO

    def test_resolves_ifc_path_to_absolute(self, tmp_path: Path) -> None:
        ifc = tmp_path / "model.ifc"
        ifc.write_text("stub")
        cfg = RenderConfig(ifc_path=ifc, project_id="p1", output_dir=tmp_path)
        assert cfg.ifc_path.is_absolute()

    def test_raises_if_ifc_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="IFC no encontrado"):
            RenderConfig(
                ifc_path=tmp_path / "no_existe.ifc",
                project_id="p1",
                output_dir=tmp_path,
            )

    def test_2k_defaults(self, tmp_path: Path) -> None:
        ifc = tmp_path / "model.ifc"
        ifc.write_text("stub")
        cfg = RenderConfig(ifc_path=ifc, project_id="p1", output_dir=tmp_path)
        assert cfg.render_width == 2048
        assert cfg.render_height == 1152

    def test_custom_samples(self, tmp_path: Path) -> None:
        ifc = tmp_path / "model.ifc"
        ifc.write_text("stub")
        cfg = RenderConfig(ifc_path=ifc, project_id="p1", output_dir=tmp_path, samples=128)
        assert cfg.samples == 128


class TestRenderResult:
    def test_empty_result(self) -> None:
        result = RenderResult(
            project_id="p1",
            output_dir=Path("/tmp"),
            views=[],
            total_duration_seconds=0.0,
        )
        assert result.views == []
        assert result.warnings == []

    def test_view_fields(self) -> None:
        view = RenderView(name="exterior_34", output_path=Path("/tmp/a.png"), duration_seconds=12.5)
        assert view.name == "exterior_34"
        assert view.duration_seconds == 12.5


# ---------------------------------------------------------------------------
# Clasificación IFC → material
# ---------------------------------------------------------------------------


class _FakeProduct:
    """Stub mínimo de producto IFC para tests."""

    def __init__(self, ifc_class: str, name: str = "") -> None:
        self._cls = ifc_class
        self.Name = name
        self.PredefinedType = None
        self.GlobalId = "TEST000"
        self.Representation = object()  # truthy

    def is_a(self) -> str:
        return self._cls


class TestIfcProductToMaterial:
    def test_exterior_wall(self) -> None:
        p = _FakeProduct("IfcWallStandardCase", "storey-0-ext-0")
        assert _ifc_product_to_material(p) == "mat_wall_exterior"

    def test_interior_wall(self) -> None:
        p = _FakeProduct("IfcWallStandardCase", "storey-0-int-3")
        assert _ifc_product_to_material(p) == "mat_wall_interior"

    def test_floor_slab(self) -> None:
        p = _FakeProduct("IfcSlab", "storey-0-slab-floor")
        p.PredefinedType = "BASESLAB"
        assert _ifc_product_to_material(p) == "mat_slab_floor"

    def test_roof_slab(self) -> None:
        p = _FakeProduct("IfcSlab", "slab-roof")
        p.PredefinedType = "ROOF"
        assert _ifc_product_to_material(p) == "mat_slab_roof"

    def test_door(self) -> None:
        p = _FakeProduct("IfcDoor", "door-0")
        assert _ifc_product_to_material(p) == "mat_door"

    def test_window(self) -> None:
        p = _FakeProduct("IfcWindow", "window-1")
        assert _ifc_product_to_material(p) == "mat_window"

    def test_generic_fallback(self) -> None:
        p = _FakeProduct("IfcFurniture", "chair")
        assert _ifc_product_to_material(p) == "mat_generic"


# ---------------------------------------------------------------------------
# Cámaras
# ---------------------------------------------------------------------------


class TestComputeCameras:
    def _bbox(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        w: float = 30.0,
        d: float = 20.0,
        h: float = 12.0,
    ) -> dict:
        return {
            "min": [x, y, z],
            "max": [x + w, y + d, z + h],
            "center": [x + w / 2, y + d / 2, z + h / 2],
        }

    def test_returns_four_cameras(self) -> None:
        cameras = compute_cameras(self._bbox(), north_angle_deg=0.0)
        assert len(cameras) == 4

    def test_camera_names(self) -> None:
        cameras = compute_cameras(self._bbox(), north_angle_deg=0.0)
        names = {c["name"] for c in cameras}
        assert "exterior_34" in names
        assert "aerial" in names
        assert "interior_0" in names
        assert "interior_1" in names

    def test_aerial_camera_above_roof(self) -> None:
        bbox = self._bbox(h=12.0)
        cameras = compute_cameras(bbox, north_angle_deg=0.0)
        aerial = next(c for c in cameras if c["name"] == "aerial")
        assert aerial["position"][2] > bbox["max"][2]

    def test_interior_cameras_at_eye_height(self) -> None:
        bbox = self._bbox(z=0.0, h=12.0)
        cameras = compute_cameras(bbox, north_angle_deg=0.0)
        for cam in cameras:
            if cam["name"].startswith("interior_"):
                eye_z = cam["position"][2]
                # 1.6 m sobre el nivel del suelo
                assert abs(eye_z - 1.6) < 0.01, f"{cam['name']} eye_z={eye_z}"

    def test_north_angle_rotates_exterior_camera(self) -> None:
        bbox = self._bbox()
        cam_0 = compute_cameras(bbox, north_angle_deg=0.0)
        cam_90 = compute_cameras(bbox, north_angle_deg=90.0)
        ext_0 = cam_0[0]["position"][:2]
        ext_90 = cam_90[0]["position"][:2]
        # Posiciones distintas cuando el norte cambia
        assert not (abs(ext_0[0] - ext_90[0]) < 0.01 and abs(ext_0[1] - ext_90[1]) < 0.01)

    def test_cameras_have_lens_field(self) -> None:
        cameras = compute_cameras(self._bbox(), north_angle_deg=0.0)
        for cam in cameras:
            assert "lens_mm" in cam
            assert cam["lens_mm"] > 0


# ---------------------------------------------------------------------------
# Extracción OBJ (requiere el IFC de referencia)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _EXAMPLE_IFC.exists(), reason="IFC de referencia no disponible")
class TestExtractGeometryToObj:
    def test_creates_obj_and_mtl(self, tmp_path: Path) -> None:
        obj_path = tmp_path / "geometry.obj"
        extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        assert obj_path.exists()
        assert obj_path.with_suffix(".mtl").exists()

    def test_obj_not_empty(self, tmp_path: Path) -> None:
        obj_path = tmp_path / "geometry.obj"
        extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        content = obj_path.read_text(encoding="utf-8")
        # Debe haber vértices y caras
        assert "v " in content
        assert "f " in content

    def test_bounding_box_keys(self, tmp_path: Path) -> None:
        obj_path = tmp_path / "geometry.obj"
        bbox = extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        assert {"min", "max", "center"} == set(bbox.keys())

    def test_bounding_box_plausible_for_residential(self, tmp_path: Path) -> None:
        obj_path = tmp_path / "geometry.obj"
        bbox = extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        dx = bbox["max"][0] - bbox["min"][0]
        dy = bbox["max"][1] - bbox["min"][1]
        dz = bbox["max"][2] - bbox["min"][2]
        # Edificio residencial razonable: entre 3 m y 200 m en cada dimensión
        assert 3.0 < dx < 200.0, f"dx={dx}"
        assert 3.0 < dy < 200.0, f"dy={dy}"
        assert 2.0 < dz < 60.0, f"dz={dz}"

    def test_obj_uses_material_groups(self, tmp_path: Path) -> None:
        obj_path = tmp_path / "geometry.obj"
        extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        content = obj_path.read_text(encoding="utf-8")
        assert "usemtl" in content
        # Al menos muros y losas deben aparecer
        assert "mat_wall_" in content or "mat_slab_" in content

    def test_obj_face_indices_valid(self, tmp_path: Path) -> None:
        """Verifica que todos los índices de cara referencien vértices existentes."""
        obj_path = tmp_path / "geometry.obj"
        extract_geometry_to_obj(_EXAMPLE_IFC, obj_path)
        vertex_count = 0
        max_index_seen = 0
        for line in obj_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("v "):
                vertex_count += 1
            elif line.startswith("f "):
                indices = [int(t.split("/")[0]) for t in line.split()[1:]]
                max_index_seen = max(max_index_seen, max(indices))
        assert max_index_seen <= vertex_count, (
            f"Índice de cara {max_index_seen} > vértices {vertex_count}"
        )


# ---------------------------------------------------------------------------
# Parser de output de Blender
# ---------------------------------------------------------------------------


class TestParseRenderResults:
    def test_parses_render_view_lines(self, tmp_path: Path) -> None:
        stdout = (
            "Importando OBJ...\n"
            "RENDER_VIEW exterior_34 23.4\n"
            "RENDER_VIEW aerial 18.1\n"
            "RENDER_DEVICE HIP\n"
        )
        views, device = _parse_render_results(stdout, tmp_path)
        assert len(views) == 2
        assert views[0].name == "exterior_34"
        assert abs(views[0].duration_seconds - 23.4) < 0.001
        assert views[1].name == "aerial"
        assert device == "HIP"

    def test_device_defaults_to_cpu_if_absent(self, tmp_path: Path) -> None:
        stdout = "RENDER_VIEW ext 10.0\n"
        _, device = _parse_render_results(stdout, tmp_path)
        assert device == "CPU"

    def test_empty_stdout_returns_empty(self, tmp_path: Path) -> None:
        views, device = _parse_render_results("", tmp_path)
        assert views == []
        assert device == "CPU"

    def test_malformed_duration_defaults_to_zero(self, tmp_path: Path) -> None:
        stdout = "RENDER_VIEW exterior_34 bad_number\n"
        views, _ = _parse_render_results(stdout, tmp_path)
        assert views[0].duration_seconds == 0.0
