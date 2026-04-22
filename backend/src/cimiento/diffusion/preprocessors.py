"""Preprocesadores de imagen para los modos ControlNet."""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_CANNY_THRESHOLD_LOW = 100
_CANNY_THRESHOLD_HIGH = 200


def extract_canny(image_rgb: np.ndarray) -> np.ndarray:
    """Devuelve un mapa de bordes Canny en escala de grises (H×W×3, uint8)."""
    import cv2

    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, _CANNY_THRESHOLD_LOW, _CANNY_THRESHOLD_HIGH)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)


def extract_depth(image_rgb: np.ndarray, *, model_id: str, device: str) -> np.ndarray:
    """Estima profundidad con DPT-MiDaS y devuelve mapa normalizado (H×W×3, uint8).

    Eleva RuntimeError si la inferencia falla, para que el caller pueda hacer
    fallback a canny.
    """
    try:
        from PIL import Image
        from transformers import DPTForDepthEstimation, DPTImageProcessor

        processor = DPTImageProcessor.from_pretrained(model_id)
        model = DPTForDepthEstimation.from_pretrained(model_id)
        model.to(device)
        model.eval()

        import torch

        pil_image = Image.fromarray(image_rgb)
        inputs = processor(images=pil_image, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            depth = outputs.predicted_depth

        depth_np = depth.squeeze().cpu().numpy()
        depth_min, depth_max = depth_np.min(), depth_np.max()
        if depth_max > depth_min:
            depth_normalized = (depth_np - depth_min) / (depth_max - depth_min)
        else:
            depth_normalized = np.zeros_like(depth_np)

        depth_uint8 = (depth_normalized * 255).astype(np.uint8)
        import cv2

        depth_resized = cv2.resize(
            depth_uint8,
            (image_rgb.shape[1], image_rgb.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        return cv2.cvtColor(depth_resized, cv2.COLOR_GRAY2RGB)

    except Exception as exc:
        raise RuntimeError(f"Depth estimation failed: {exc}") from exc
