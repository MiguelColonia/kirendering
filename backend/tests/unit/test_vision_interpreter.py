"""Tests del intérprete VLM para planos (Fase 7)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from cimiento.schemas.typology import RoomType
from cimiento.schemas.vision import (
    DetectedLabel,
    DetectedSymbol,
    PixelBBox,
    PlanInterpretation,
    RoomRegion,
    SymbolType,
)
from cimiento.vision.interpreter import (
    _build_draft_building,
    _extract_json,
    _parse_labels,
    _parse_room_regions,
    _parse_symbols,
    combine_preprocessing_and_vlm,
    estimate_room_types,
    identify_symbols,
    read_labels,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_floor_plan(width: int = 400, height: int = 300) -> np.ndarray:
    """Genera un plano sintético en escala de grises con muros y texto."""
    img = np.full((height, width), 255, dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (width - 10, height - 10), 0, 3)
    cv2.line(img, (width // 2, 10), (width // 2, height - 10), 0, 2)
    cv2.line(img, (10, height // 2), (width - 10, height // 2), 0, 2)
    cv2.putText(img, "Wohnzimmer", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
    cv2.putText(img, "Schlafzimmer", (width // 2 + 10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
    cv2.putText(img, "Küche", (20, height // 2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
    cv2.putText(
        img, "Bad", (width // 2 + 10, height // 2 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1
    )
    return img


def _mock_vlm_response(content: str) -> MagicMock:
    """Crea un mock de OllamaChatResponse con el contenido dado."""
    response = MagicMock()
    response.content = content
    return response


def _make_vlm_client(response_content: str) -> AsyncMock:
    """Crea un OllamaClient mock que devuelve siempre el mismo contenido."""
    client = AsyncMock()
    client.chat = AsyncMock(return_value=_mock_vlm_response(response_content))
    return client


# ---------------------------------------------------------------------------
# Tests de helpers privados
# ---------------------------------------------------------------------------


def test_extract_json_from_plain_json() -> None:
    payload = '{"symbols": []}'
    assert _extract_json(payload) == {"symbols": []}


def test_extract_json_from_wrapped_text() -> None:
    payload = 'Here is the result:\n{"rooms": []}\nDone.'
    assert _extract_json(payload) == {"rooms": []}


def test_extract_json_returns_empty_on_failure() -> None:
    assert _extract_json("no json here at all") == {}


def test_parse_symbols_valid() -> None:
    payload = {
        "symbols": [
            {"type": "DOOR", "bbox_px": [10, 20, 30, 40], "confidence": 0.9},
            {"type": "WINDOW", "bbox_px": [100, 50, 20, 15], "confidence": 0.7},
        ]
    }
    symbols = _parse_symbols(payload)
    assert len(symbols) == 2
    assert symbols[0].symbol_type == SymbolType.DOOR
    assert symbols[0].confidence == pytest.approx(0.9)
    assert symbols[1].symbol_type == SymbolType.WINDOW


def test_parse_symbols_invalid_bbox_skipped() -> None:
    payload = {
        "symbols": [
            {"type": "DOOR", "bbox_px": [10, 20], "confidence": 0.8},
            {"type": "STAIR", "bbox_px": [5, 5, 20, 30], "confidence": 0.6},
        ]
    }
    symbols = _parse_symbols(payload)
    assert len(symbols) == 1
    assert symbols[0].symbol_type == SymbolType.STAIR


def test_parse_symbols_unknown_type_mapped() -> None:
    payload = {"symbols": [{"type": "WARDROBE", "bbox_px": [0, 0, 10, 10], "confidence": 0.3}]}
    symbols = _parse_symbols(payload)
    assert symbols[0].symbol_type == SymbolType.UNKNOWN


def test_parse_labels_valid() -> None:
    payload = {
        "labels": [
            {"text": "Wohnzimmer", "room_type": "LIVING", "bbox_px": [10, 10, 80, 20]},
            {"text": "Bad", "room_type": "BATHROOM", "bbox_px": [200, 150, 40, 20]},
        ]
    }
    labels = _parse_labels(payload)
    assert len(labels) == 2
    assert labels[0].raw_text == "Wohnzimmer"
    assert labels[0].room_type == RoomType.LIVING
    assert labels[1].room_type == RoomType.BATHROOM


def test_parse_labels_null_room_type() -> None:
    payload = {"labels": [{"text": "Maßstab 1:100", "room_type": None, "bbox_px": [5, 5, 60, 10]}]}
    labels = _parse_labels(payload)
    assert labels[0].room_type is None


def test_parse_labels_empty_text_skipped() -> None:
    payload = {"labels": [{"text": "", "room_type": "LIVING", "bbox_px": [0, 0, 10, 10]}]}
    assert _parse_labels(payload) == []


def test_parse_room_regions_valid() -> None:
    payload = {
        "rooms": [
            {
                "label": "Wohnzimmer",
                "room_type": "LIVING",
                "center_px": [100, 80],
                "bbox_px": [10, 10, 180, 140],
            },
            {
                "label": "Küche",
                "room_type": "KITCHEN",
                "center_px": [300, 80],
                "bbox_px": [210, 10, 180, 140],
            },
        ]
    }
    regions = _parse_room_regions(payload)
    assert len(regions) == 2
    assert regions[0].room_type == RoomType.LIVING
    assert regions[0].center_px == (100, 80)
    assert regions[1].room_type == RoomType.KITCHEN


def test_parse_room_regions_invalid_room_type_skipped() -> None:
    payload = {
        "rooms": [
            {
                "label": "X",
                "room_type": "ROOF_TERRACE",
                "center_px": [50, 50],
                "bbox_px": [0, 0, 100, 100],
            },
            {
                "label": "Bad",
                "room_type": "BATHROOM",
                "center_px": [200, 50],
                "bbox_px": [100, 0, 100, 100],
            },
        ]
    }
    regions = _parse_room_regions(payload)
    assert len(regions) == 1
    assert regions[0].room_type == RoomType.BATHROOM


# ---------------------------------------------------------------------------
# Tests de funciones públicas async (con VLM mock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identify_symbols_returns_list() -> None:
    symbols_json = json.dumps(
        {
            "symbols": [
                {"type": "DOOR", "bbox_px": [50, 10, 20, 5], "confidence": 0.95},
                {"type": "WINDOW", "bbox_px": [100, 10, 25, 5], "confidence": 0.85},
            ]
        }
    )
    client = _make_vlm_client(symbols_json)
    img = _make_floor_plan()

    result = await identify_symbols(img, client)

    assert len(result) == 2
    assert all(isinstance(s, DetectedSymbol) for s in result)
    client.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_identify_symbols_empty_response() -> None:
    client = _make_vlm_client('{"symbols": []}')
    img = _make_floor_plan()
    result = await identify_symbols(img, client)
    assert result == []


@pytest.mark.asyncio
async def test_read_labels_german_labels() -> None:
    labels_json = json.dumps(
        {
            "labels": [
                {"text": "Wohnzimmer", "room_type": "LIVING", "bbox_px": [20, 40, 90, 18]},
                {"text": "Schlafzimmer", "room_type": "BEDROOM", "bbox_px": [210, 40, 95, 18]},
                {"text": "Küche", "room_type": "KITCHEN", "bbox_px": [20, 165, 50, 18]},
                {"text": "Bad", "room_type": "BATHROOM", "bbox_px": [210, 165, 35, 18]},
            ]
        }
    )
    client = _make_vlm_client(labels_json)
    img = _make_floor_plan()

    result = await read_labels(img, client)

    assert len(result) == 4
    assert all(isinstance(lb, DetectedLabel) for lb in result)
    room_types = {lb.raw_text: lb.room_type for lb in result}
    assert room_types["Wohnzimmer"] == RoomType.LIVING
    assert room_types["Küche"] == RoomType.KITCHEN


@pytest.mark.asyncio
async def test_read_labels_infers_room_type_from_german_text() -> None:
    labels_json = json.dumps(
        {
            "labels": [
                {"text": "Flur", "room_type": None, "bbox_px": [10, 10, 30, 12]},
            ]
        }
    )
    client = _make_vlm_client(labels_json)
    img = _make_floor_plan()

    result = await read_labels(img, client)

    assert result[0].room_type == RoomType.CORRIDOR


@pytest.mark.asyncio
async def test_estimate_room_types_returns_regions() -> None:
    rooms_json = json.dumps(
        {
            "rooms": [
                {
                    "label": "Wohnzimmer",
                    "room_type": "LIVING",
                    "center_px": [100, 75],
                    "bbox_px": [10, 10, 180, 130],
                },
                {
                    "label": "Schlafzimmer",
                    "room_type": "BEDROOM",
                    "center_px": [300, 75],
                    "bbox_px": [210, 10, 180, 130],
                },
            ]
        }
    )
    client = _make_vlm_client(rooms_json)
    img = _make_floor_plan()

    result = await estimate_room_types(img, client)

    assert len(result) == 2
    assert all(isinstance(r, RoomRegion) for r in result)


# ---------------------------------------------------------------------------
# Tests de _build_draft_building
# ---------------------------------------------------------------------------


def _make_minimal_interpretation(
    *,
    meters_per_pixel: float | None = 0.05,
    room_regions: list[RoomRegion] | None = None,
    wall_segments: list | None = None,
) -> PlanInterpretation:
    from cimiento.schemas.vision import WallSegmentPx

    if room_regions is None:
        room_regions = [
            RoomRegion(
                label_text="Wohnzimmer",
                room_type=RoomType.LIVING,
                center_px=(100, 75),
                approx_bbox_px=PixelBBox(x=10, y=10, width=180, height=130),
            )
        ]
    if wall_segments is None:
        wall_segments = [WallSegmentPx(x1=10, y1=10, x2=190, y2=10)]

    return PlanInterpretation(
        image_path="/tmp/plan.png",
        image_width_px=400,
        image_height_px=300,
        meters_per_pixel=meters_per_pixel,
        room_regions=room_regions,
        wall_segments_px=wall_segments,
    )


def test_build_draft_building_returns_building_with_scale() -> None:
    interp = _make_minimal_interpretation(meters_per_pixel=0.05)
    building = _build_draft_building(interp, project_id="p1", solar_id="s1")
    assert building is not None
    assert building.project_id == "p1"
    assert len(building.storeys) == 1
    assert len(building.storeys[0].spaces) == 1
    assert building.storeys[0].spaces[0].room_type == RoomType.LIVING


def test_build_draft_building_returns_none_without_scale() -> None:
    interp = _make_minimal_interpretation(meters_per_pixel=None)
    building = _build_draft_building(interp, project_id="p1", solar_id="s1")
    assert building is None


def test_build_draft_building_skips_degenerate_regions() -> None:

    bad_region = RoomRegion(
        label_text=None,
        room_type=RoomType.BEDROOM,
        center_px=(5, 5),
        approx_bbox_px=PixelBBox(x=0, y=0, width=1, height=1),
    )
    interp = _make_minimal_interpretation(
        meters_per_pixel=1e-10,
        room_regions=[bad_region],
        wall_segments=[],
    )
    building = _build_draft_building(interp, project_id="p1", solar_id="s1")
    assert building is None


def test_build_draft_building_walls_converted_to_meters() -> None:
    from cimiento.schemas.vision import WallSegmentPx

    interp = _make_minimal_interpretation(
        meters_per_pixel=0.1,
        wall_segments=[WallSegmentPx(x1=0, y1=0, x2=100, y2=0)],
    )
    building = _build_draft_building(interp, project_id="p1", solar_id="s1")
    assert building is not None
    wall = building.storeys[0].walls[0]
    assert wall.start_point.x == pytest.approx(0.0)
    assert wall.end_point.x == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Test de integración del pipeline completo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_combine_preprocessing_and_vlm_full_pipeline(tmp_path: Path) -> None:
    img_path = tmp_path / "plan.png"
    plan = _make_floor_plan()
    cv2.imwrite(str(img_path), plan)

    symbols_resp = json.dumps(
        {"symbols": [{"type": "DOOR", "bbox_px": [195, 10, 10, 5], "confidence": 0.9}]}
    )
    labels_resp = json.dumps(
        {"labels": [{"text": "Wohnzimmer", "room_type": "LIVING", "bbox_px": [20, 45, 90, 18]}]}
    )
    rooms_resp = json.dumps(
        {
            "rooms": [
                {
                    "label": "Wohnzimmer",
                    "room_type": "LIVING",
                    "center_px": [100, 75],
                    "bbox_px": [10, 10, 180, 130],
                }
            ]
        }
    )

    call_count = 0
    responses = [symbols_resp, labels_resp, rooms_resp]

    async def _chat_side_effect(*args: object, **kwargs: object) -> MagicMock:
        nonlocal call_count
        content = responses[call_count % len(responses)]
        call_count += 1
        return _mock_vlm_response(content)

    client = AsyncMock()
    client.chat = AsyncMock(side_effect=_chat_side_effect)

    with patch(
        "cimiento.vision.interpreter.extract_scale",
        new_callable=lambda: lambda *a, **kw: _async_return(0.05),
    ):
        result = await combine_preprocessing_and_vlm(
            img_path, client, project_id="p1", solar_id="s1"
        )

    assert isinstance(result, PlanInterpretation)
    assert result.is_draft is True
    assert result.review_required is True
    assert result.image_width_px > 0
    assert result.image_height_px > 0
    assert result.meters_per_pixel == pytest.approx(0.05)
    assert len(result.detected_symbols) == 1
    assert len(result.detected_labels) == 1
    assert len(result.room_regions) == 1
    assert result.draft_building is not None
    assert len(result.draft_building.storeys) == 1


async def _async_return(value: object) -> object:
    return value


@pytest.mark.asyncio
async def test_combine_preprocessing_and_vlm_no_scale_produces_none_building(
    tmp_path: Path,
) -> None:
    img_path = tmp_path / "plan.png"
    cv2.imwrite(str(img_path), _make_floor_plan())

    empty_json = json.dumps({"symbols": [], "labels": [], "rooms": []})

    client = AsyncMock()
    client.chat = AsyncMock(return_value=_mock_vlm_response(empty_json))

    with patch(
        "cimiento.vision.interpreter.extract_scale",
        new_callable=lambda: lambda *a, **kw: _async_return(None),
    ):
        result = await combine_preprocessing_and_vlm(img_path, client)

    assert result.draft_building is None
    assert result.meters_per_pixel is None
    assert any("maßstab" in w.lower() or "scale" in w.lower() for w in result.warnings)
