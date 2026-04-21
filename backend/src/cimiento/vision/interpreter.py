"""
Interpretación semántica de planos con VLM (qwen2.5vl:7b).

Las funciones públicas de este módulo reciben una imagen ya normalizada
(output de `preprocessing.load_and_normalize`) y un cliente VLM, y devuelven
anotaciones semánticas sobre el plano.

LIMITACIÓN FUNDAMENTAL: todo output de este módulo es aproximado y requiere
revisión humana. `combine_preprocessing_and_vlm` produce un `PlanInterpretation`
con `draft_building` cuyo uso como entrada directa del solver está prohibido
sin confirmación explícita del usuario (ver `PlanInterpretation.review_required`).
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from pydantic import ValidationError

from cimiento.llm.client import OllamaChatMessage, OllamaClient
from cimiento.schemas.architectural import Building, Space, Storey, Wall, WallType
from cimiento.schemas.geometry_primitives import Point2D, Polygon2D
from cimiento.schemas.typology import RoomType
from cimiento.schemas.vision import (
    DetectedLabel,
    DetectedSymbol,
    PixelBBox,
    PlanInterpretation,
    RoomRegion,
    SymbolType,
    WallSegmentPx,
)
from cimiento.vision.preprocessing import (
    ImageArray,
    detect_lines,
    detect_text_regions,
    extract_scale,
    load_and_normalize,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_GERMAN_LABEL_TO_ROOM_TYPE: dict[str, RoomType] = {
    "wohnzimmer": RoomType.LIVING,
    "wohn": RoomType.LIVING,
    "wohnessen": RoomType.LIVING,
    "wohn-esszimmer": RoomType.LIVING,
    "esszimmer": RoomType.LIVING,
    "wohnraum": RoomType.LIVING,
    "balkon": RoomType.LIVING,
    "terrasse": RoomType.LIVING,
    "loggia": RoomType.LIVING,
    "küche": RoomType.KITCHEN,
    "kuche": RoomType.KITCHEN,
    "küchenzeile": RoomType.KITCHEN,
    "kochnische": RoomType.KITCHEN,
    "schlafzimmer": RoomType.BEDROOM,
    "kinderzimmer": RoomType.BEDROOM,
    "gästezimmer": RoomType.BEDROOM,
    "gastezimmer": RoomType.BEDROOM,
    "zimmer": RoomType.BEDROOM,
    "bad": RoomType.BATHROOM,
    "badezimmer": RoomType.BATHROOM,
    "wc": RoomType.BATHROOM,
    "dusche": RoomType.BATHROOM,
    "duschbad": RoomType.BATHROOM,
    "flur": RoomType.CORRIDOR,
    "diele": RoomType.CORRIDOR,
    "gang": RoomType.CORRIDOR,
    "korridor": RoomType.CORRIDOR,
    "treppenhaus": RoomType.CORRIDOR,
    "eingang": RoomType.CORRIDOR,
    "vorraum": RoomType.CORRIDOR,
    "abstellraum": RoomType.STORAGE,
    "abstellkammer": RoomType.STORAGE,
    "kammer": RoomType.STORAGE,
    "speisekammer": RoomType.STORAGE,
    "lager": RoomType.STORAGE,
    "hauswirtschaft": RoomType.STORAGE,
    "hwraum": RoomType.STORAGE,
    "garage": RoomType.PARKING,
    "stellplatz": RoomType.PARKING,
    "carport": RoomType.PARKING,
    "tiefgarage": RoomType.PARKING,
}

_SYMBOL_PROMPT = (
    "Analyze this architectural floor plan. Identify all architectural symbols: "
    "doors (Türen), windows (Fenster), stairs (Treppen), and structural columns (Stützen). "
    "Return ONLY valid JSON with key \"symbols\", a list where each item has:\n"
    "- \"type\": one of \"DOOR\", \"WINDOW\", \"STAIR\", \"COLUMN\", \"UNKNOWN\"\n"
    "- \"bbox_px\": [x, y, width, height] in pixels (top-left origin)\n"
    "- \"confidence\": float 0.0-1.0\n"
    "If no symbols are found, return {\"symbols\": []}."
)

_LABELS_PROMPT = (
    "Analyze this architectural floor plan. Find all room labels "
    "(German text such as Wohnzimmer, Schlafzimmer, Küche, Bad, Flur, etc.). "
    "Return ONLY valid JSON with key \"labels\", a list where each item has:\n"
    "- \"text\": exact text as visible in the plan\n"
    "- \"room_type\": one of \"LIVING\", \"KITCHEN\", \"BEDROOM\", \"BATHROOM\", "
    "\"CORRIDOR\", \"STORAGE\", \"PARKING\", or null if not a room label\n"
    "- \"bbox_px\": [x, y, width, height] approximate bounding box in pixels\n"
    "If no labels found, return {\"labels\": []}."
)

_ROOMS_PROMPT = (
    "Analyze this architectural floor plan. Identify ALL enclosed rooms and spaces. "
    "For each room, determine its type from shape, size, fixtures, and visible labels. "
    "Return ONLY valid JSON with key \"rooms\", a list where each item has:\n"
    "- \"label\": visible label text or a descriptive name if no label is visible\n"
    "- \"room_type\": one of \"LIVING\", \"KITCHEN\", \"BEDROOM\", \"BATHROOM\", "
    "\"CORRIDOR\", \"STORAGE\", \"PARKING\"\n"
    "- \"center_px\": [x, y] approximate center in pixels\n"
    "- \"bbox_px\": [x, y, width, height] approximate bounding box in pixels\n"
    "If no rooms found, return {\"rooms\": []}."
)

# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _require_cv2() -> Any:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV no está disponible. Instale `opencv-python-headless` en el entorno backend."
        )
    return cv2


def _encode_image_base64(img: ImageArray) -> str:
    """Codifica una imagen NumPy en base64 PNG para enviarla al VLM."""
    cv = _require_cv2()
    ok, encoded = cv.imencode(".png", img)
    if not ok:
        raise ValueError("No se pudo codificar la imagen como PNG.")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _extract_json(text: str) -> dict[str, Any]:
    """Extrae el primer bloque JSON de una respuesta de texto del VLM."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _safe_bbox(raw: Any) -> PixelBBox | None:
    """Construye un PixelBBox a partir de [x, y, w, h] o None si los datos son inválidos."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 4:
        return None
    try:
        x, y, w, h = int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            return None
        return PixelBBox(x=x, y=y, width=w, height=h)
    except (TypeError, ValueError):
        return None


def _parse_symbol_type(raw: str) -> SymbolType:
    """Convierte una cadena de texto en SymbolType con fallback a UNKNOWN."""
    try:
        return SymbolType(raw.upper())
    except ValueError:
        return SymbolType.UNKNOWN


def _parse_room_type_str(raw: str | None) -> RoomType | None:
    """Convierte una cadena en RoomType probando el enum y el diccionario alemán."""
    if not raw:
        return None
    upper = raw.upper()
    try:
        return RoomType(upper)
    except ValueError:
        pass
    normalized = raw.lower().strip()
    return _GERMAN_LABEL_TO_ROOM_TYPE.get(normalized)


def _parse_symbols(payload: dict[str, Any]) -> list[DetectedSymbol]:
    """Construye DetectedSymbol desde el JSON devuelto por el VLM."""
    results: list[DetectedSymbol] = []
    for item in payload.get("symbols", []):
        if not isinstance(item, dict):
            continue
        bbox = _safe_bbox(item.get("bbox_px"))
        if bbox is None:
            continue
        try:
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5
        results.append(
            DetectedSymbol(
                symbol_type=_parse_symbol_type(str(item.get("type", "UNKNOWN"))),
                bbox_px=bbox,
                confidence=confidence,
            )
        )
    return results


def _parse_labels(payload: dict[str, Any]) -> list[DetectedLabel]:
    """Construye DetectedLabel desde el JSON devuelto por el VLM."""
    results: list[DetectedLabel] = []
    for item in payload.get("labels", []):
        if not isinstance(item, dict):
            continue
        bbox = _safe_bbox(item.get("bbox_px"))
        if bbox is None:
            continue
        raw_text = str(item.get("text", "")).strip()
        if not raw_text:
            continue
        room_type = _parse_room_type_str(item.get("room_type"))
        results.append(DetectedLabel(bbox_px=bbox, raw_text=raw_text, room_type=room_type))
    return results


def _parse_room_regions(payload: dict[str, Any]) -> list[RoomRegion]:
    """Construye RoomRegion desde el JSON devuelto por el VLM."""
    results: list[RoomRegion] = []
    for item in payload.get("rooms", []):
        if not isinstance(item, dict):
            continue
        bbox = _safe_bbox(item.get("bbox_px"))
        if bbox is None:
            continue
        room_type = _parse_room_type_str(item.get("room_type"))
        if room_type is None:
            continue
        center_raw = item.get("center_px")
        if isinstance(center_raw, (list, tuple)) and len(center_raw) >= 2:
            try:
                center: tuple[int, int] = (int(center_raw[0]), int(center_raw[1]))
            except (TypeError, ValueError):
                center = (bbox.center_x, bbox.center_y)
        else:
            center = (bbox.center_x, bbox.center_y)
        label_text = str(item.get("label", "")).strip() or None
        results.append(
            RoomRegion(
                label_text=label_text,
                room_type=room_type,
                center_px=center,
                approx_bbox_px=bbox,
            )
        )
    return results


def _build_draft_building(
    interpretation: PlanInterpretation,
    project_id: str,
    solar_id: str,
) -> Building | None:
    """
    Intenta construir un Building borrador a partir de la interpretación visual.

    Devuelve None si la escala es desconocida o si los datos son insuficientes
    para crear al menos un espacio válido. La geometría se deriva multiplicando
    las coordenadas en píxeles por `meters_per_pixel`.
    """
    mpp = interpretation.meters_per_pixel
    if mpp is None or mpp <= 0.0:
        return None

    spaces: list[Space] = []
    for i, region in enumerate(interpretation.room_regions):
        bbox = region.approx_bbox_px
        x0 = float(bbox.x) * mpp
        y0 = float(bbox.y) * mpp
        x1 = float(bbox.x + bbox.width) * mpp
        y1 = float(bbox.y + bbox.height) * mpp
        if abs(x1 - x0) < 1e-6 or abs(y1 - y0) < 1e-6:
            continue
        try:
            contour = Polygon2D(
                points=[
                    Point2D(x=x0, y=y0),
                    Point2D(x=x1, y=y0),
                    Point2D(x=x1, y=y1),
                    Point2D(x=x0, y=y1),
                ]
            )
            spaces.append(
                Space(
                    id=f"space_{i}",
                    name=region.label_text or region.room_type.value.capitalize(),
                    contour=contour,
                    floor_level=0,
                    room_type=region.room_type,
                )
            )
        except ValidationError:
            continue

    walls: list[Wall] = []
    for i, seg in enumerate(interpretation.wall_segments_px):
        start = Point2D(x=float(seg.x1) * mpp, y=float(seg.y1) * mpp)
        end = Point2D(x=float(seg.x2) * mpp, y=float(seg.y2) * mpp)
        if start.x == end.x and start.y == end.y:
            continue
        try:
            walls.append(
                Wall(
                    id=f"wall_{i}",
                    start_point=start,
                    end_point=end,
                    height_m=2.7,
                    thickness_m=0.2,
                    wall_type=WallType.PARTITION,
                )
            )
        except ValidationError:
            continue

    if not spaces and not walls:
        return None

    storey = Storey(
        id="storey_0",
        level=0,
        elevation_m=0.0,
        height_m=2.7,
        name="Planta Baja (borrador)",
        spaces=spaces,
        walls=walls,
    )

    draft_id = f"draft_{uuid.uuid4().hex[:8]}"
    try:
        return Building(
            id=draft_id,
            name="Borrador visual (requiere revisión)",
            project_id=project_id,
            solar_id=solar_id,
            storeys=[storey],
            metadata={"source": "vision", "is_draft": "true"},
        )
    except ValidationError:
        return None


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------


async def identify_symbols(
    img: ImageArray,
    vlm_client: OllamaClient,
) -> list[DetectedSymbol]:
    """
    Pide al VLM que identifique puertas, ventanas, escaleras y columnas en el plano.

    La imagen debe estar normalizada (output de `load_and_normalize`). El VLM
    devuelve cajas delimitadoras aproximadas en píxeles para cada símbolo.
    """
    image_b64 = _encode_image_base64(img)
    message = OllamaChatMessage(role="user", content=_SYMBOL_PROMPT, images=[image_b64])
    response = await vlm_client.chat([message], role="vision", format="json")
    payload = _extract_json(response.content)
    return _parse_symbols(payload)


async def read_labels(
    img: ImageArray,
    vlm_client: OllamaClient,
) -> list[DetectedLabel]:
    """
    Reconoce etiquetas de estancias en el plano combinando regiones de texto (OpenCV)
    con lectura e interpretación semántica (VLM).

    Primero detecta regiones de texto con `detect_text_regions` y luego envía la
    imagen completa al VLM con contexto sobre las etiquetas esperadas (alemán).
    Las regiones de texto detectadas por OpenCV sirven para calibrar las cajas
    devueltas por el VLM cuando existen discrepancias evidentes.
    """
    ocr_regions = detect_text_regions(img)

    context = ""
    if ocr_regions:
        region_list = "; ".join(
            f"({x},{y},{w},{h})" for x, y, w, h in ocr_regions[:20]
        )
        context = (
            f"\nOpenCV detected {len(ocr_regions)} text region candidates at: {region_list}. "
            "Use these as hints for bounding boxes but rely on visual content for text."
        )

    prompt = _LABELS_PROMPT + context
    image_b64 = _encode_image_base64(img)
    message = OllamaChatMessage(role="user", content=prompt, images=[image_b64])
    response = await vlm_client.chat([message], role="vision", format="json")
    payload = _extract_json(response.content)
    labels = _parse_labels(payload)

    for label in labels:
        if label.room_type is None:
            label_room_type = _parse_room_type_str(label.raw_text)
            if label_room_type is not None:
                object.__setattr__(label, "room_type", label_room_type)

    return labels


async def estimate_room_types(
    img: ImageArray,
    vlm_client: OllamaClient,
) -> list[RoomRegion]:
    """
    Clasifica cada región cerrada del plano a un RoomType del schema.

    El VLM analiza la imagen completa e identifica estancias por su forma, tamaño,
    mobiliario representado y etiquetas visibles. Cada región devuelta incluye un
    RoomType del enum canónico y una caja delimitadora aproximada en píxeles.
    """
    image_b64 = _encode_image_base64(img)
    message = OllamaChatMessage(role="user", content=_ROOMS_PROMPT, images=[image_b64])
    response = await vlm_client.chat([message], role="vision", format="json")
    payload = _extract_json(response.content)
    return _parse_room_regions(payload)


async def combine_preprocessing_and_vlm(
    image_path: str | Path,
    vlm_client: OllamaClient,
    *,
    project_id: str = "draft",
    solar_id: str = "draft",
) -> PlanInterpretation:
    """
    Fusiona los outputs geométricos de OpenCV con los semánticos del VLM.

    Pipeline completo:
    1. `load_and_normalize` — rectificación de perspectiva y normalización.
    2. `detect_lines` — segmentos de muro por HoughLinesP.
    3. `extract_scale` — escala métrica desde barra o cotas del plano.
    4. `identify_symbols` — puertas, ventanas, escaleras vía VLM.
    5. `read_labels` — etiquetas de estancias vía OCR + VLM.
    6. `estimate_room_types` — clasificación funcional de regiones vía VLM.
    7. `_build_draft_building` — modelo BIM borrador (requiere escala válida).

    El objeto devuelto siempre tiene `is_draft=True` y `review_required=True`.
    El `draft_building` es None si no se dispone de escala métrica fiable.

    ADVERTENCIA: NO usar `draft_building` como entrada del solver sin confirmación
    y corrección explícita del usuario.
    """
    warnings: list[str] = []
    path = Path(image_path)
    img: NDArray[np.uint8] = load_and_normalize(path)
    height_px, width_px = img.shape[:2]

    line_segments = detect_lines(img)
    wall_segments_px = [
        WallSegmentPx(x1=p1[0], y1=p1[1], x2=p2[0], y2=p2[1])
        for p1, p2 in line_segments
    ]

    meters_per_pixel = await extract_scale(img, vlm_client)
    if meters_per_pixel is None:
        warnings.append(
            "No se encontró barra de escala ni referencia dimensional. "
            "Las coordenadas en píxeles no pueden convertirse a metros. "
            "draft_building será None."
        )

    symbols = await identify_symbols(img, vlm_client)
    labels = await read_labels(img, vlm_client)
    room_regions = await estimate_room_types(img, vlm_client)

    if not symbols:
        warnings.append(
            "El VLM no detectó ningún símbolo arquitectónico (puertas, ventanas, etc.)."
        )
    if not labels:
        warnings.append("No se reconocieron etiquetas de estancias en el plano.")
    if not room_regions:
        warnings.append("El VLM no identificó ninguna región de estancia en el plano.")

    interpretation = PlanInterpretation(
        image_path=str(path.resolve()),
        image_width_px=width_px,
        image_height_px=height_px,
        meters_per_pixel=meters_per_pixel,
        detected_symbols=symbols,
        detected_labels=labels,
        room_regions=room_regions,
        wall_segments_px=wall_segments_px,
        warnings=warnings,
    )

    draft = _build_draft_building(interpretation, project_id=project_id, solar_id=solar_id)
    if draft is None and meters_per_pixel is not None:
        warnings.append(
            "No se pudo construir un Building borrador: "
            "datos insuficientes (sin estancias ni muros válidos tras conversión)."
        )

    return PlanInterpretation(
        image_path=str(path.resolve()),
        image_width_px=width_px,
        image_height_px=height_px,
        meters_per_pixel=meters_per_pixel,
        detected_symbols=symbols,
        detected_labels=labels,
        room_regions=room_regions,
        wall_segments_px=wall_segments_px,
        draft_building=draft,
        warnings=warnings,
    )


__all__ = [
    "combine_preprocessing_and_vlm",
    "estimate_room_types",
    "identify_symbols",
    "read_labels",
]
