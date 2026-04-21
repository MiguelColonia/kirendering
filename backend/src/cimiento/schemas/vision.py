"""
Schemas de salida de la capa de visión (Fase 7).

Representan los resultados del análisis VLM sobre un plano escaneado: símbolos
arquitectónicos detectados, etiquetas de estancias, regiones identificadas y el
edificio borrador resultante de fusionar la geometría OpenCV con la semántica VLM.

IMPORTANTE: todos los objetos de este módulo son borradores aproximados. El campo
`review_required` siempre es True y el output NO puede usarse como entrada directa
del solver sin confirmación explícita del usuario.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from cimiento.schemas.architectural import Building
from cimiento.schemas.typology import RoomType


class SymbolType(StrEnum):
    """Tipo de símbolo arquitectónico identificado en planta."""

    DOOR = "DOOR"
    WINDOW = "WINDOW"
    STAIR = "STAIR"
    COLUMN = "COLUMN"
    UNKNOWN = "UNKNOWN"


class PixelBBox(BaseModel):
    """Caja delimitadora en coordenadas de píxel (origen en esquina superior izquierda)."""

    x: int = Field(..., ge=0, description="Coordenada X del extremo superior izquierdo")
    y: int = Field(..., ge=0, description="Coordenada Y del extremo superior izquierdo")
    width: int = Field(..., gt=0, description="Anchura en píxeles")
    height: int = Field(..., gt=0, description="Altura en píxeles")

    @property
    def center_x(self) -> int:
        """Coordenada X del centro de la caja."""
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        """Coordenada Y del centro de la caja."""
        return self.y + self.height // 2


class DetectedSymbol(BaseModel):
    """
    Símbolo arquitectónico localizado por el VLM en la imagen del plano.

    La posición se expresa en píxeles de la imagen original normalizada (tras
    `load_and_normalize`). La confianza es subjetiva y proviene del propio VLM;
    no debe interpretarse como probabilidad estadística calibrada.
    """

    symbol_type: SymbolType = Field(..., description="Tipo de símbolo detectado")
    bbox_px: PixelBBox = Field(
        ...,
        description="Caja delimitadora del símbolo en píxeles de la imagen normalizada",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza subjetiva del VLM (0.0–1.0); no es probabilidad calibrada",
    )


class DetectedLabel(BaseModel):
    """
    Etiqueta de texto encontrada en el plano mediante reconocimiento óptico asistido por VLM.

    `room_type` es None cuando el texto no se puede mapear a ningún tipo funcional
    conocido (p. ej. notas de escala, firmas, números de parcela).
    """

    bbox_px: PixelBBox = Field(
        ...,
        description="Caja delimitadora aproximada de la etiqueta en píxeles",
    )
    raw_text: str = Field(..., description="Texto tal como aparece en el plano")
    room_type: RoomType | None = Field(
        default=None,
        description="Tipo funcional inferido del texto; None si no corresponde a estancia",
    )


class RoomRegion(BaseModel):
    """
    Región cerrada del plano identificada y clasificada por el VLM como estancia.

    La geometría es aproximada: el VLM estima cajas delimitadoras, no contornos
    exactos. La conversión a metros requiere que `PlanInterpretation.meters_per_pixel`
    sea no nulo.
    """

    label_text: str | None = Field(
        default=None,
        description="Etiqueta visible en el plano para esta estancia, si existe",
    )
    room_type: RoomType = Field(..., description="Tipo funcional clasificado por el VLM")
    center_px: tuple[int, int] = Field(
        ...,
        description="Coordenadas (x, y) del centro aproximado de la estancia en píxeles",
    )
    approx_bbox_px: PixelBBox = Field(
        ...,
        description="Caja delimitadora aproximada de la estancia en píxeles",
    )


class WallSegmentPx(BaseModel):
    """Segmento de muro detectado por HoughLinesP, en coordenadas de píxel."""

    x1: int = Field(..., description="Coordenada X del extremo inicial")
    y1: int = Field(..., description="Coordenada Y del extremo inicial")
    x2: int = Field(..., description="Coordenada X del extremo final")
    y2: int = Field(..., description="Coordenada Y del extremo final")


class PlanInterpretation(BaseModel):
    """
    Resultado combinado del análisis geométrico (OpenCV) y semántico (VLM) de un plano.

    ADVERTENCIA: este objeto es siempre un borrador aproximado que REQUIERE revisión
    humana antes de cualquier uso. Los campos `is_draft` y `review_required` están
    fijados en True de forma permanente y documentan esta limitación.

    `draft_building` es None cuando los datos son insuficientes para construir un
    modelo BIM mínimamente coherente (p. ej. si no se encontró escala métrica).
    Incluso cuando no es None, el edificio borrador NO puede usarse como entrada
    directa del solver sin confirmación y corrección por parte del usuario.
    """

    image_path: str = Field(..., description="Ruta de la imagen analizada")
    image_width_px: int = Field(
        ..., gt=0, description="Anchura de la imagen normalizada en píxeles"
    )
    image_height_px: int = Field(
        ..., gt=0, description="Altura de la imagen normalizada en píxeles"
    )
    meters_per_pixel: float | None = Field(
        default=None,
        description=(
            "Escala estimada en metros/píxel. None si no se encontró barra de escala "
            "ni referencia dimensional fiable."
        ),
    )
    detected_symbols: list[DetectedSymbol] = Field(
        default_factory=list,
        description="Puertas, ventanas, escaleras y columnas identificadas por el VLM",
    )
    detected_labels: list[DetectedLabel] = Field(
        default_factory=list,
        description="Etiquetas de texto reconocidas mediante OCR asistido por VLM",
    )
    room_regions: list[RoomRegion] = Field(
        default_factory=list,
        description="Estancias identificadas y clasificadas por el VLM",
    )
    wall_segments_px: list[WallSegmentPx] = Field(
        default_factory=list,
        description="Segmentos de muro detectados por HoughLinesP en píxeles",
    )
    draft_building: Building | None = Field(
        default=None,
        description=(
            "Edificio borrador construido a partir del análisis. None si la escala es "
            "desconocida o los datos son insuficientes. REQUIERE revisión humana."
        ),
    )
    is_draft: bool = Field(
        default=True,
        description="Siempre True: el output de visión es siempre un borrador aproximado",
    )
    review_required: bool = Field(
        default=True,
        description="Siempre True: revisión humana obligatoria antes de usar el resultado",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Advertencias del proceso de análisis (datos faltantes, baja confianza, etc.)",
    )
