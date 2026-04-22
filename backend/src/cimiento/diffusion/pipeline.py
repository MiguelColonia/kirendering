"""Orquestador del pipeline de difusión con caché lazy de modelos."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from cimiento.schemas.diffusion import DiffusionConfig, DiffusionMode, DiffusionResult

logger = logging.getLogger(__name__)

_LOADED_PIPELINES: dict[str, Any] = {}
_TARGET_SIZE = (512, 512)


def _detect_device() -> str:
    import torch

    if torch.version.hip is not None:
        return "cuda"
    if torch.cuda.is_available():
        return "cuda"
    logger.warning("Sin GPU disponible; usando CPU para difusión (rendimiento reducido)")
    return "cpu"


def _load_controlnet_pipeline(mode: DiffusionMode, settings: Any) -> Any:
    """Carga (o devuelve desde caché) el pipeline ControlNet para el modo dado."""
    key = mode.value
    if key in _LOADED_PIPELINES:
        return _LOADED_PIPELINES[key]

    import torch
    from diffusers import ControlNetModel, StableDiffusionControlNetPipeline

    device = _detect_device()
    dtype = torch.float16 if device == "cuda" else torch.float32
    kwargs = {"cache_dir": settings.hf_cache_dir} if settings.hf_cache_dir else {}

    controlnet_model_id = (
        settings.sd_controlnet_depth_model
        if mode == DiffusionMode.IMG2IMG_CONTROLNET_DEPTH
        else settings.sd_controlnet_canny_model
    )

    controlnet = ControlNetModel.from_pretrained(controlnet_model_id, torch_dtype=dtype, **kwargs)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        settings.sd_base_model, controlnet=controlnet, torch_dtype=dtype, **kwargs
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()

    _LOADED_PIPELINES[key] = (pipe, device)
    return (pipe, device)


def _load_pix2pix_pipeline(settings: Any) -> tuple[Any, str]:
    key = DiffusionMode.INSTRUCT_PIX2PIX.value
    if key in _LOADED_PIPELINES:
        return _LOADED_PIPELINES[key]

    import torch
    from diffusers import StableDiffusionInstructPix2PixPipeline

    device = _detect_device()
    dtype = torch.float16 if device == "cuda" else torch.float32
    kwargs = {"cache_dir": settings.hf_cache_dir} if settings.hf_cache_dir else {}

    pipe = StableDiffusionInstructPix2PixPipeline.from_pretrained(
        settings.sd_instruct_pix2pix_model,
        torch_dtype=dtype,
        safety_checker=None,
        **kwargs,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()

    _LOADED_PIPELINES[key] = (pipe, device)
    return (pipe, device)


def _read_image_rgb(path: Path) -> Any:
    import cv2

    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        raise ValueError(f"No se pudo leer la imagen: {path}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgb = cv2.resize(img_rgb, _TARGET_SIZE, interpolation=cv2.INTER_LANCZOS4)
    return img_rgb


def run_diffusion(config: DiffusionConfig, *, settings: Any | None = None) -> DiffusionResult:
    """Ejecuta el pipeline de difusión según el modo configurado."""
    if settings is None:
        from cimiento.core.config import settings as _settings

        settings = _settings

    from PIL import Image

    start = time.monotonic()
    warnings_list: list[str] = []

    img_rgb = _read_image_rgb(config.input_image_path)
    input_pil = Image.fromarray(img_rgb)

    generator = None
    if config.seed is not None:
        import torch

        generator = torch.Generator().manual_seed(config.seed)

    if config.mode == DiffusionMode.INSTRUCT_PIX2PIX:
        pipe, device = _load_pix2pix_pipeline(settings)
        result_images = pipe(
            config.prompt,
            image=input_pil,
            num_inference_steps=config.num_inference_steps,
            image_guidance_scale=config.image_guidance_scale,
            guidance_scale=config.guidance_scale,
            generator=generator,
        ).images

    else:
        from cimiento.diffusion.preprocessors import extract_canny, extract_depth

        if config.mode == DiffusionMode.IMG2IMG_CONTROLNET_DEPTH:
            try:
                control_map = extract_depth(
                    img_rgb,
                    model_id=settings.sd_depth_estimator_model,
                    device=_detect_device(),
                )
            except RuntimeError as exc:
                logger.warning("Depth estimation failed, falling back to canny: %s", exc)
                warnings_list.append("Tiefenschätzung fehlgeschlagen — Canny-Fallback verwendet.")
                control_map = extract_canny(img_rgb)
        else:
            control_map = extract_canny(img_rgb)

        control_pil = Image.fromarray(control_map)
        pipe, device = _load_controlnet_pipeline(config.mode, settings)
        result_images = pipe(
            config.prompt,
            image=input_pil,
            control_image=control_pil,
            negative_prompt=config.negative_prompt or None,
            num_inference_steps=config.num_inference_steps,
            guidance_scale=config.guidance_scale,
            controlnet_conditioning_scale=config.controlnet_conditioning_scale,
            generator=generator,
        ).images

    output_image: Image.Image = result_images[0]
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"diffusion_{config.mode.value}.png"
    output_path = config.output_dir / output_filename
    output_image.save(output_path, format="PNG")

    duration = time.monotonic() - start
    device_used = _detect_device()

    return DiffusionResult(
        project_id=config.project_id,
        mode=config.mode,
        output_path=output_path,
        duration_seconds=round(duration, 2),
        device_used=device_used.upper(),
        width=output_image.width,
        height=output_image.height,
        warnings=warnings_list,
    )
