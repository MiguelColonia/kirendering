"""Endpoints de análisis visual de planos (Fase 7)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, status

from cimiento.api.dependencies import get_output_root, get_repository
from cimiento.api.errors import api_error, project_not_found
from cimiento.api.schemas import (
    DetectedLabelResponse,
    DetectedSymbolResponse,
    PixelBBoxResponse,
    PlanInterpretationResponse,
    RoomRegionResponse,
)
from cimiento.llm.client import OllamaClient
from cimiento.persistence.repository import ProjectRepository
from cimiento.schemas.vision import PlanInterpretation
from cimiento.vision import combine_preprocessing_and_vlm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["vision"])

_PLAN_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def _get_vlm_client(request: Request) -> OllamaClient:
    return request.app.state.chat_client


def _serialize_interpretation(interp: PlanInterpretation) -> PlanInterpretationResponse:
    return PlanInterpretationResponse(
        image_width_px=interp.image_width_px,
        image_height_px=interp.image_height_px,
        meters_per_pixel=interp.meters_per_pixel,
        detected_symbols=[
            DetectedSymbolResponse(
                symbol_type=s.symbol_type.value,
                bbox_px=PixelBBoxResponse(
                    x=s.bbox_px.x,
                    y=s.bbox_px.y,
                    width=s.bbox_px.width,
                    height=s.bbox_px.height,
                ),
                confidence=s.confidence,
            )
            for s in interp.detected_symbols
        ],
        detected_labels=[
            DetectedLabelResponse(
                bbox_px=PixelBBoxResponse(
                    x=lb.bbox_px.x,
                    y=lb.bbox_px.y,
                    width=lb.bbox_px.width,
                    height=lb.bbox_px.height,
                ),
                raw_text=lb.raw_text,
                room_type=lb.room_type.value if lb.room_type else None,
            )
            for lb in interp.detected_labels
        ],
        room_regions=[
            RoomRegionResponse(
                label_text=r.label_text,
                room_type=r.room_type.value,
                center_px=r.center_px,
                approx_bbox_px=PixelBBoxResponse(
                    x=r.approx_bbox_px.x,
                    y=r.approx_bbox_px.y,
                    width=r.approx_bbox_px.width,
                    height=r.approx_bbox_px.height,
                ),
            )
            for r in interp.room_regions
        ],
        wall_segment_count=len(interp.wall_segments_px),
        has_draft_building=interp.draft_building is not None,
        is_draft=interp.is_draft,
        review_required=interp.review_required,
        warnings=interp.warnings,
    )


@router.post(
    "/projects/{project_id}/vision/analyze",
    response_model=PlanInterpretationResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_plan(
    project_id: str,
    file: UploadFile,
    request: Request,
    repository: ProjectRepository = Depends(get_repository),
    output_root: Path = Depends(get_output_root),
) -> PlanInterpretationResponse:
    """Analiza visualmente un plano y devuelve el borrador de interpretación."""
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _PLAN_EXTENSIONS:
        raise api_error(status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_PLAN_IMAGE")

    plans_dir = output_root / project_id / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex[:12]}_{Path(file.filename or 'plan').name}"
    image_path = plans_dir / unique_name

    content = await file.read()
    image_path.write_bytes(content)
    logger.info("Plano guardado en '%s' para el proyecto '%s'", image_path, project_id)

    vlm_client: OllamaClient = _get_vlm_client(request)

    try:
        interpretation = await combine_preprocessing_and_vlm(
            image_path,
            vlm_client,
            project_id=project_id,
        )
    except Exception as exc:
        logger.exception("Fallo en análisis visual del plano para proyecto '%s'", project_id)
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "VISION_ANALYSIS_FAILED") from exc

    return _serialize_interpretation(interpretation)
