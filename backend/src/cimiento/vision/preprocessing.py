"""
Preprocesado OpenCV para limpiar y vectorizar planos arquitectónicos antes del VLM.

Responsabilidades de este módulo (capa Visión, ADR 0012):
  1. Carga y normalización de la imagen (``load_and_normalize``).
     Corrige perspectiva si detecta un documento fotográfico (cuadrilátero > 18% del área).
  2. Binarización adaptativa (``binarize``) con threshold gaussiano para tolerar
     variaciones de iluminación en fotografías de planos impresos.
  3. Detección de segmentos de muro con HoughLinesP (``detect_lines``).
     Los parámetros por defecto están calibrados para planos A1/A2 escaneados a 150-300 dpi.
  4. Detección de regiones de texto/cotas (``detect_text_regions``) mediante
     morfología de cierre + criterios de relación de aspecto y densidad de tinta.
  5. Consulta al VLM para estimación de escala métrica (``extract_scale``).
     El VLM usa ``role="vision"`` con imagen adjunta en base64 (corrección del bug
     documentado en CHANGELOG [Unreleased] — antes usaba ``role="chat"`` sin imagen).

Invariante: ninguna función de este módulo modifica el IFC ni alimenta al solver
directamente. Todo output es "borrador pendiente de revisión humana" (ADR 0012).
"""

from __future__ import annotations

import base64
import inspect
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeAlias

import numpy as np
from numpy.typing import NDArray

try:
    import cv2
except ImportError:  # pragma: no cover - se valida en runtime y en entorno real.
    cv2 = None

ImageArray: TypeAlias = NDArray[np.uint8]
LineSegment: TypeAlias = tuple[tuple[int, int], tuple[int, int]]
BoundingBox: TypeAlias = tuple[int, int, int, int]

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_METERS_PER_PIXEL_RE = re.compile(
    r"(?P<value>\d+(?:[\.,]\d+)?)\s*(?:m|metros?|meters?)\s*/\s*(?:px|pixel(?:es)?)",
    re.IGNORECASE,
)
_PIXELS_PER_METER_RE = re.compile(
    r"(?P<value>\d+(?:[\.,]\d+)?)\s*(?:px|pixel(?:es)?)\s*/\s*(?:m|metros?|meters?)",
    re.IGNORECASE,
)


def load_and_normalize(path: str | Path) -> ImageArray:
    """Carga una imagen de plano, la rectifica si detecta documento y la normaliza en gris."""
    cv = _require_cv2()
    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(f"No existe la imagen: {image_path}")

    image = cv.imread(str(image_path), cv.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"No se pudo cargar la imagen: {image_path}")

    corrected = _correct_document_perspective(image)
    grayscale = _ensure_grayscale(corrected)
    normalized = cv.normalize(grayscale, None, alpha=0, beta=255, norm_type=cv.NORM_MINMAX)
    return normalized.astype(np.uint8)


def binarize(img: ImageArray, *, block_size: int = 25, c: int = 11) -> ImageArray:
    """Aplica umbralización adaptativa sobre una imagen en gris."""
    cv = _require_cv2()
    grayscale = _ensure_grayscale(img)
    normalized_block_size = _ensure_odd(block_size)
    blurred = cv.GaussianBlur(grayscale, (5, 5), 0)
    binary = cv.adaptiveThreshold(
        blurred,
        255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        normalized_block_size,
        c,
    )
    return binary.astype(np.uint8)


def detect_lines(
    img: ImageArray,
    *,
    rho: float = 1.0,
    theta: float = np.pi / 180,
    threshold: int = 80,
    min_line_length: int = 40,
    max_line_gap: int = 12,
) -> list[LineSegment]:
    """Detecta segmentos lineales dominantes con HoughLinesP."""
    cv = _require_cv2()
    grayscale = _ensure_grayscale(img)
    binary = binarize(grayscale)
    edges = cv.Canny(cv.bitwise_not(binary), 50, 150, apertureSize=3)
    raw_lines = cv.HoughLinesP(
        edges,
        rho=rho,
        theta=theta,
        threshold=threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )

    if raw_lines is None:
        return []

    segments = [
        ((int(line[0]), int(line[1])), (int(line[2]), int(line[3])))
        for candidate in raw_lines
        for line in candidate
    ]
    return sorted(segments, key=_segment_length, reverse=True)


def detect_text_regions(
    img: ImageArray,
    *,
    min_width: int = 18,
    min_height: int = 10,
    min_area: int = 120,
    max_area_ratio: float = 0.12,
    min_aspect_ratio: float = 0.6,
    max_aspect_ratio: float = 18.0,
) -> list[BoundingBox]:
    """Localiza regiones compactas que se comportan como cotas, leyendas o etiquetas."""
    cv = _require_cv2()
    grayscale = _ensure_grayscale(img)
    binary_inv = cv.bitwise_not(binarize(grayscale))
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (9, 3))
    connected = cv.morphologyEx(binary_inv, cv.MORPH_CLOSE, kernel, iterations=1)
    connected = cv.dilate(connected, cv.getStructuringElement(cv.MORPH_RECT, (3, 3)), iterations=1)
    contours, _ = cv.findContours(connected, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    total_area = grayscale.shape[0] * grayscale.shape[1]
    regions: list[BoundingBox] = []
    for contour in contours:
        x, y, width, height = cv.boundingRect(contour)
        box_area = width * height
        aspect_ratio = width / max(height, 1)

        if width < min_width or height < min_height:
            continue
        if box_area < min_area or box_area > total_area * max_area_ratio:
            continue
        if not min_aspect_ratio <= aspect_ratio <= max_aspect_ratio:
            continue

        contour_fill = cv.contourArea(contour) / max(box_area, 1)
        if not 0.08 <= contour_fill <= 0.95:
            continue

        ink_ratio = float(np.count_nonzero(binary_inv[y : y + height, x : x + width])) / box_area
        if not 0.08 <= ink_ratio <= 0.95:
            continue

        regions.append((x, y, width, height))

    return sorted(regions, key=lambda region: (region[1], region[0]))


async def extract_scale(img: ImageArray, vlm_client: Any) -> float | None:
    """Pide al VLM una estimación de escala y devuelve metros por píxel si es interpretable."""
    cv = _require_cv2()
    grayscale = _ensure_grayscale(img)
    ok, encoded = cv.imencode(".png", grayscale)
    if not ok:
        raise ValueError("No se pudo codificar la imagen para enviarla al VLM.")

    image_base64 = base64.b64encode(encoded.tobytes()).decode("ascii")
    prompt = (
        "Analyze this architectural floor plan. Find any scale bar, dimension line, or "
        "measurement reference visible in the image. "
        "Return ONLY valid JSON with one of these keys: "
        "`meters_per_pixel` (float) or `pixels_per_meter` (float). "
        "If you cannot estimate reliably, return {\"meters_per_pixel\": null}."
    )

    if hasattr(vlm_client, "extract_scale"):
        response = vlm_client.extract_scale(
            prompt=prompt,
            image_base64=image_base64,
            image_shape=grayscale.shape,
        )
    elif hasattr(vlm_client, "chat"):
        messages = [{"role": "user", "content": prompt, "images": [image_base64]}]
        try:
            response = vlm_client.chat(messages=messages, role="vision", format="json")
        except TypeError:
            response = vlm_client.chat(messages=messages)
    else:
        raise TypeError("El VLM debe exponer `extract_scale(...)` o `chat(...)`.")

    resolved_response = await _maybe_await(response)
    return _parse_scale_response(resolved_response)


def _require_cv2() -> Any:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV no está disponible. Instale `opencv-python-headless` en el entorno backend."
        )
    return cv2


def _ensure_grayscale(img: ImageArray) -> ImageArray:
    cv = _require_cv2()
    if img.ndim == 2:
        return img.astype(np.uint8)
    if img.ndim != 3:
        raise ValueError(f"Se esperaba una imagen 2D o 3D, se recibió shape={img.shape!r}")
    if img.shape[2] == 3:
        return cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    if img.shape[2] == 4:
        return cv.cvtColor(img, cv.COLOR_BGRA2GRAY)
    raise ValueError(f"Número de canales no soportado: {img.shape[2]}")


def _correct_document_perspective(img: ImageArray) -> ImageArray:
    cv = _require_cv2()
    grayscale = _ensure_grayscale(img)
    blurred = cv.GaussianBlur(grayscale, (5, 5), 0)
    edges = cv.Canny(blurred, 60, 180)
    closed = cv.morphologyEx(
        edges,
        cv.MORPH_CLOSE,
        cv.getStructuringElement(cv.MORPH_RECT, (5, 5)),
        iterations=2,
    )
    contours, _ = cv.findContours(closed, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    image_area = grayscale.shape[0] * grayscale.shape[1]
    for contour in sorted(contours, key=cv.contourArea, reverse=True):
        area = cv.contourArea(contour)
        if area < image_area * 0.18:
            continue

        perimeter = cv.arcLength(contour, True)
        approx = cv.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            corners = approx.reshape(4, 2).astype(np.float32)
        else:
            rect = cv.minAreaRect(contour)
            corners = cv.boxPoints(rect).astype(np.float32)

        return _warp_from_corners(img, _order_points(corners))

    return img


def _warp_from_corners(img: ImageArray, corners: NDArray[np.float32]) -> ImageArray:
    cv = _require_cv2()
    top_left, top_right, bottom_right, bottom_left = corners
    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    width = max(int(round(max(width_a, width_b))), 1)
    height = max(int(round(max(height_a, height_b))), 1)

    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv.getPerspectiveTransform(corners, destination)
    return cv.warpPerspective(img, matrix, (width, height))


def _order_points(points: NDArray[np.float32]) -> NDArray[np.float32]:
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(diffs)]
    ordered[3] = points[np.argmax(diffs)]
    return ordered


def _segment_length(segment: LineSegment) -> float:
    (x1, y1), (x2, y2) = segment
    return math.hypot(x2 - x1, y2 - y1)


def _ensure_odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _parse_scale_response(response: Any) -> float | None:
    payload = _coerce_response_payload(response)
    parsed = _parse_scale_mapping(payload) if isinstance(payload, Mapping) else None
    if parsed is not None:
        return parsed

    text = payload if isinstance(payload, str) else json.dumps(payload)
    json_match = _JSON_BLOCK_RE.search(text)
    if json_match:
        try:
            parsed_json = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            parsed_json = None
        if isinstance(parsed_json, Mapping):
            parsed = _parse_scale_mapping(parsed_json)
            if parsed is not None:
                return parsed

    meters_match = _METERS_PER_PIXEL_RE.search(text)
    if meters_match:
        return _to_float(meters_match.group("value"))

    pixels_match = _PIXELS_PER_METER_RE.search(text)
    if pixels_match:
        pixels_per_meter = _to_float(pixels_match.group("value"))
        return None if pixels_per_meter in (None, 0.0) else 1.0 / pixels_per_meter

    return None


def _coerce_response_payload(response: Any) -> Mapping[str, Any] | str:
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "content"):
        return str(response.content)
    if hasattr(response, "message"):
        message = response.message
        if isinstance(message, Mapping):
            content = message.get("content")
            if content is not None:
                return str(content)
    return str(response)


def _parse_scale_mapping(payload: Mapping[str, Any]) -> float | None:
    meters_value = payload.get("meters_per_pixel")
    if meters_value is not None:
        return _to_float(meters_value)

    pixels_value = payload.get("pixels_per_meter")
    if pixels_value is not None:
        pixels_per_meter = _to_float(pixels_value)
        return None if pixels_per_meter in (None, 0.0) else 1.0 / pixels_per_meter

    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


__all__ = [
    "BoundingBox",
    "ImageArray",
    "LineSegment",
    "binarize",
    "detect_lines",
    "detect_text_regions",
    "extract_scale",
    "load_and_normalize",
]
