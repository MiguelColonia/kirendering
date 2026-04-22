"""Schemas Pydantic para el pipeline de difusión."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class DiffusionMode(StrEnum):
    IMG2IMG_CONTROLNET_DEPTH = "img2img_controlnet_depth"
    IMG2IMG_CONTROLNET_CANNY = "img2img_controlnet_canny"
    INSTRUCT_PIX2PIX = "instruct_pix2pix"


class DiffusionConfig(BaseModel):
    project_id: str
    mode: DiffusionMode
    input_image_path: Path
    output_dir: Path
    prompt: str
    negative_prompt: str = ""
    num_inference_steps: int = 20
    guidance_scale: float = 7.5
    image_guidance_scale: float = 1.5
    controlnet_conditioning_scale: float = 1.0
    seed: int | None = None
    timeout_seconds: int = 600


class DiffusionResult(BaseModel):
    project_id: str
    mode: DiffusionMode
    output_path: Path
    duration_seconds: float
    device_used: str
    width: int = 512
    height: int = 512
    warnings: list[str] = Field(default_factory=list)
