"""Tests unitarios del endpoint POST /api/projects/{id}/vision/analyze."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from cimiento.api.main import create_app
from cimiento.schemas import Program, Typology, TypologyMix
from cimiento.schemas.vision import PlanInterpretation

pytest_plugins = ["tests.fixtures.valid_cases"]


# ---------------------------------------------------------------------------
# Helpers y fixtures
# ---------------------------------------------------------------------------


async def _ok(_: object) -> dict[str, str]:
    return {"status": "ok"}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'vision-unit.db'}",
        output_root=tmp_path / "outputs",
        health_checks={"ollama": _ok, "qdrant": _ok},
    )
    with TestClient(app) as c:
        yield c


def _minimal_png() -> bytes:
    """Imagen PNG 20×20 px sintética sin procesar con VLM real."""
    img = np.full((20, 20, 3), 200, dtype=np.uint8)
    cv2.line(img, (2, 10), (18, 10), (0, 0, 0), 1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _fake_interpretation(image_path: str = "/tmp/plan.png") -> PlanInterpretation:
    return PlanInterpretation(
        image_path=image_path,
        image_width_px=20,
        image_height_px=20,
        meters_per_pixel=0.02,
        warnings=["Test-Warnung: kein echter VLM verwendet."],
    )


def _create_project(
    client: TestClient,
    sample_solar_rectangular,
    sample_typology_t2: Typology,
) -> str:
    program = Program(
        project_id="tmp",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=3)],
    )
    response = client.post(
        "/api/projects",
        json={
            "name": "Vision-Test-Projekt",
            "solar": sample_solar_rectangular.model_dump(mode="json"),
            "program": program.model_dump(mode="json"),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Tests: validación de entrada
# ---------------------------------------------------------------------------


class TestVisionAnalyzeInputValidation:
    def test_returns_404_when_project_does_not_exist(self, client: TestClient) -> None:
        # When: se analiza un plano de un proyecto inexistente
        response = client.post(
            "/api/projects/proyecto-inexistente/vision/analyze",
            files={"file": ("plan.png", _minimal_png(), "image/png")},
        )

        # Then: 404 con código estándar en alemán
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
        assert response.json()["error"]["message"] == "Das Projekt wurde nicht gefunden."

    def test_returns_400_for_unsupported_extension(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        # When: se sube un PDF como plano
        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("plano.pdf", b"%PDF-1.4", "application/pdf")},
        )

        # Then: 400 con código de imagen no soportada
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "UNSUPPORTED_PLAN_IMAGE"

    def test_returns_400_for_txt_extension(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("notas.txt", b"esto no es un plano", "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "UNSUPPORTED_PLAN_IMAGE"


# ---------------------------------------------------------------------------
# Tests: ejecución del pipeline (VLM mockeado)
# ---------------------------------------------------------------------------


class TestVisionAnalyzePipeline:
    def test_returns_200_and_plan_interpretation_with_valid_png(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        # Monkeypatch: evita llamadas reales al VLM
        async def fake_combine(image_path, vlm_client, *, project_id="draft", solar_id="draft"):
            return _fake_interpretation(str(image_path))

        monkeypatch.setattr(
            "cimiento.api.routers.vision.combine_preprocessing_and_vlm", fake_combine
        )

        # When: se sube un PNG válido
        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("grundriss.png", _minimal_png(), "image/png")},
        )

        # Then: responde 200 con la interpretación
        assert response.status_code == 200
        payload = response.json()
        assert payload["image_width_px"] == 20
        assert payload["image_height_px"] == 20
        assert payload["meters_per_pixel"] == pytest.approx(0.02)
        assert payload["is_draft"] is True
        assert payload["review_required"] is True
        assert isinstance(payload["warnings"], list)

    def test_accepts_jpg_extension(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        async def fake_combine(image_path, vlm_client, **kwargs):
            return _fake_interpretation(str(image_path))

        monkeypatch.setattr(
            "cimiento.api.routers.vision.combine_preprocessing_and_vlm", fake_combine
        )

        img = np.full((10, 10, 3), 180, dtype=np.uint8)
        ok, buf = cv2.imencode(".jpg", img)
        assert ok

        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("foto.jpg", buf.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 200

    def test_returns_500_when_vlm_raises(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        async def broken_combine(*args, **kwargs):
            raise RuntimeError("Ollama no disponible en este entorno de test")

        monkeypatch.setattr(
            "cimiento.api.routers.vision.combine_preprocessing_and_vlm", broken_combine
        )

        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("plan.png", _minimal_png(), "image/png")},
        )

        # Then: 500 con código VISION_ANALYSIS_FAILED
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "VISION_ANALYSIS_FAILED"

    def test_saves_image_to_project_plans_directory(
        self,
        tmp_path: Path,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app = create_app(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'save-test.db'}",
            output_root=tmp_path / "outputs",
            health_checks={"ollama": _ok, "qdrant": _ok},
        )

        saved_paths: list[str] = []

        async def capture_path(image_path, vlm_client, **kwargs):
            saved_paths.append(str(image_path))
            return _fake_interpretation(str(image_path))

        monkeypatch.setattr(
            "cimiento.api.routers.vision.combine_preprocessing_and_vlm", capture_path
        )

        with TestClient(app) as c:
            program = Program(
                project_id="tmp",
                num_floors=1,
                floor_height_m=3.0,
                typologies=[sample_typology_t2],
                mix=[TypologyMix(typology_id="T2", count=2)],
            )
            project_id = c.post(
                "/api/projects",
                json={
                    "name": "Save-Test",
                    "solar": sample_solar_rectangular.model_dump(mode="json"),
                    "program": program.model_dump(mode="json"),
                },
            ).json()["id"]

            c.post(
                f"/api/projects/{project_id}/vision/analyze",
                files={"file": ("grundriss.png", _minimal_png(), "image/png")},
            )

        # Then: la imagen se guardó dentro del directorio de planes del proyecto
        assert len(saved_paths) == 1
        saved = Path(saved_paths[0])
        assert saved.parent.name == "plans"
        assert saved.parent.parent.name == project_id
        assert saved.suffix == ".png"


# ---------------------------------------------------------------------------
# Tests: serialización de la respuesta
# ---------------------------------------------------------------------------


class TestVisionResponseSchema:
    def test_response_contains_all_required_fields(
        self,
        client: TestClient,
        sample_solar_rectangular,
        sample_typology_t2: Typology,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project_id = _create_project(client, sample_solar_rectangular, sample_typology_t2)

        from cimiento.schemas.typology import RoomType
        from cimiento.schemas.vision import (
            DetectedLabel,
            DetectedSymbol,
            PixelBBox,
            RoomRegion,
            SymbolType,
        )

        async def fake_combine(image_path, vlm_client, **kwargs):
            return PlanInterpretation(
                image_path=str(image_path),
                image_width_px=200,
                image_height_px=150,
                meters_per_pixel=0.015,
                detected_symbols=[
                    DetectedSymbol(
                        symbol_type=SymbolType.DOOR,
                        bbox_px=PixelBBox(x=10, y=20, width=15, height=8),
                        confidence=0.85,
                    )
                ],
                detected_labels=[
                    DetectedLabel(
                        bbox_px=PixelBBox(x=50, y=60, width=40, height=12),
                        raw_text="Wohnzimmer",
                        room_type=RoomType.LIVING,
                    )
                ],
                room_regions=[
                    RoomRegion(
                        label_text="Wohnzimmer",
                        room_type=RoomType.LIVING,
                        center_px=(70, 66),
                        approx_bbox_px=PixelBBox(x=30, y=40, width=80, height=50),
                    )
                ],
                warnings=["Sin barra de escala detectada"],
            )

        monkeypatch.setattr(
            "cimiento.api.routers.vision.combine_preprocessing_and_vlm", fake_combine
        )

        response = client.post(
            f"/api/projects/{project_id}/vision/analyze",
            files={"file": ("plan.png", _minimal_png(), "image/png")},
        )

        assert response.status_code == 200
        payload = response.json()

        # Campos de imagen
        assert payload["image_width_px"] == 200
        assert payload["image_height_px"] == 150
        assert payload["meters_per_pixel"] == pytest.approx(0.015)

        # Símbolo detectado
        assert len(payload["detected_symbols"]) == 1
        sym = payload["detected_symbols"][0]
        assert sym["symbol_type"] == "DOOR"
        assert sym["confidence"] == pytest.approx(0.85)

        # Etiqueta detectada
        assert len(payload["detected_labels"]) == 1
        lbl = payload["detected_labels"][0]
        assert lbl["raw_text"] == "Wohnzimmer"
        assert lbl["room_type"] == "LIVING"

        # Región de estancia
        assert len(payload["room_regions"]) == 1
        region = payload["room_regions"][0]
        assert region["room_type"] == "LIVING"
        assert region["label_text"] == "Wohnzimmer"

        # Metadatos
        assert payload["wall_segment_count"] == 0
        assert payload["has_draft_building"] is False
        assert payload["is_draft"] is True
        assert payload["review_required"] is True
        assert "Sin barra de escala" in payload["warnings"][0]
