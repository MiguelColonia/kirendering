"""Schemas Pydantic para la capa RAG de normativa alemana de edificación."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

# Espacio de nombres UUID determinista para IDs de chunks normativos.
# Garantiza que el mismo artículo del mismo documento produce siempre el mismo ID,
# lo que permite re-indexar sin duplicar entradas en Qdrant.
_CHUNK_NAMESPACE = uuid.UUID("7f3e9c2a-4b1d-5e6f-8a0b-1c2d3e4f5678")


class RegulationChunk(BaseModel):
    """
    Unidad mínima de normativa indexada en Qdrant.

    Representa un artículo (§) o sección de un documento normativo alemán.
    El ID es determinista: mismo documento + mismo artículo = mismo UUID.
    """

    id: str = Field(..., description="UUID v5 determinista basado en documento + artículo")
    document: str = Field(
        ...,
        description="Identificador del documento normativo (p.ej. 'GEG', 'MBO', 'LBO_Bayern')",
    )
    section: str = Field(
        default="Allgemein",
        description="Sección o parte que contiene el artículo (p.ej. 'Abschnitt 3', 'Teil 2')",
    )
    article_number: str = Field(
        ...,
        description="Número de artículo según el documento (p.ej. '§ 14', 'Artikel 3')",
    )
    article_title: str = Field(
        default="",
        description="Título del artículo tal como aparece en el documento",
    )
    text: str = Field(..., description="Texto completo del artículo o sección")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales: página, fecha de publicación, etc.",
    )

    @classmethod
    def make_id(cls, document: str, article_number: str, part: int = 0) -> str:
        """Genera un UUID v5 determinista para un chunk normativo."""
        key = f"{document.upper()}/{article_number}/{part}"
        return str(uuid.uuid5(_CHUNK_NAMESPACE, key))


class RegulationSearchResult(BaseModel):
    """Resultado de una búsqueda vectorial en la base de normativa."""

    chunk: RegulationChunk
    score: float = Field(..., ge=0.0, le=1.0, description="Similitud coseno [0, 1]")
