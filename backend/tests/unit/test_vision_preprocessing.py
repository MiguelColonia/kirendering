"""Tests del preprocesado OpenCV para planos en Fase 7."""

from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from cimiento.vision.preprocessing import (
    binarize,
    detect_lines,
    detect_text_regions,
    extract_scale,
    load_and_normalize,
)


def _write_image(path: str, image: np.ndarray) -> None:
    assert cv2.imwrite(path, image)


def _build_document(width: int = 320, height: int = 440) -> np.ndarray:
    document = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(document, (8, 8), (width - 8, height - 8), (0, 0, 0), 6)
    cv2.line(document, (24, 110), (width - 24, 110), (0, 0, 0), 4)
    cv2.line(document, (width // 2, 24), (width // 2, height - 24), (0, 0, 0), 4)
    cv2.putText(
        document,
        "SCALE 1:100",
        (28, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return document


def _build_perspective_scene() -> tuple[np.ndarray, float]:
    document = _build_document()
    height, width = document.shape[:2]
    source = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    target = np.array(
        [[110, 70], [590, 115], [520, 680], [70, 620]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, target)
    scene = np.zeros((760, 760, 3), dtype=np.uint8)
    warped = cv2.warpPerspective(document, transform, (760, 760))
    mask = warped.any(axis=2)
    scene[mask] = warped[mask]
    return scene, height / width


def _overlaps(box: tuple[int, int, int, int], region: tuple[int, int, int, int]) -> bool:
    x1, y1, w1, h1 = box
    x2, y2, w2, h2 = region
    return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)


def test_load_and_normalize_rectifies_document_perspective(
    tmp_path: pytest.TempPathFactory,
) -> None:
    scene, expected_ratio = _build_perspective_scene()
    image_path = tmp_path / "plan_photo.png"
    _write_image(str(image_path), scene)

    normalized = load_and_normalize(image_path)

    assert normalized.ndim == 2
    assert normalized.dtype == np.uint8
    ratio = normalized.shape[0] / normalized.shape[1]
    assert ratio == pytest.approx(expected_ratio, rel=0.2)
    assert normalized[5:40, 5:40].mean() < 220


def test_binarize_returns_binary_image() -> None:
    image = np.full((140, 220), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 30), (190, 100), 0, -1)

    binary = binarize(image)

    unique_values = set(np.unique(binary).tolist())
    assert unique_values <= {0, 255}
    assert unique_values == {0, 255}


def test_detect_lines_returns_segments_for_wall_like_strokes() -> None:
    image = np.full((360, 360), 255, dtype=np.uint8)
    cv2.line(image, (40, 60), (320, 60), 0, 5)
    cv2.line(image, (120, 40), (120, 320), 0, 5)

    segments = detect_lines(image, threshold=35, min_line_length=120, max_line_gap=8)

    assert any(abs(y1 - y2) <= 3 and abs(x2 - x1) >= 180 for (x1, y1), (x2, y2) in segments)
    assert any(abs(x1 - x2) <= 3 and abs(y2 - y1) >= 180 for (x1, y1), (x2, y2) in segments)


def test_detect_text_regions_finds_caption_like_blocks() -> None:
    image = np.full((260, 420, 3), 255, dtype=np.uint8)
    cv2.putText(
        image,
        "Wohnung A",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        "3.20 m",
        (20, 170),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )

    regions = detect_text_regions(image)

    assert regions
    assert any(_overlaps(region, (10, 25, 240, 70)) for region in regions)
    assert any(_overlaps(region, (10, 125, 180, 70)) for region in regions)


@pytest.mark.asyncio
async def test_extract_scale_uses_dedicated_vlm_method() -> None:
    image = np.full((120, 180), 255, dtype=np.uint8)

    class StubVLM:
        def __init__(self) -> None:
            self.prompt: str | None = None
            self.image_base64: str | None = None
            self.image_shape: tuple[int, int] | None = None

        async def extract_scale(
            self,
            *,
            prompt: str,
            image_base64: str,
            image_shape: tuple[int, int],
        ) -> dict[str, float | str]:
            self.prompt = prompt
            self.image_base64 = image_base64
            self.image_shape = image_shape
            return {"meters_per_pixel": 0.025, "evidence": "barra de escala 5 m"}

    client = StubVLM()

    result = await extract_scale(image, client)

    assert result == pytest.approx(0.025)
    assert client.image_shape == image.shape
    assert client.image_base64 is not None
    assert client.prompt is not None


@pytest.mark.asyncio
async def test_extract_scale_falls_back_to_chat_response() -> None:
    image = np.full((90, 90, 3), 255, dtype=np.uint8)

    class StubChatClient:
        def __init__(self) -> None:
            self.messages: list[dict[str, object]] | None = None
            self.role: str | None = None

        async def chat(
            self,
            *,
            messages: list[dict[str, object]],
            role: str,
        ) -> SimpleNamespace:
            self.messages = messages
            self.role = role
            return SimpleNamespace(content='{"pixels_per_meter": 40}')

    client = StubChatClient()

    result = await extract_scale(image, client)

    assert result == pytest.approx(0.025)
    assert client.role == "chat"
    assert client.messages is not None
    assert client.messages[0]["images"]
