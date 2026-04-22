"""
Recuperador vectorial para normativa alemana de edificación.

Busca chunks relevantes en Qdrant mediante similitud coseno sobre embeddings
generados con nomic-embed-text, con soporte de filtros por documento y sección.
"""

from __future__ import annotations

import logging
from typing import Any

from cimiento.rag.schemas import RegulationChunk, RegulationSearchResult

log = logging.getLogger(__name__)


async def retrieve(
    query: str,
    *,
    ollama_client: Any,
    qdrant_client: Any,
    collection_name: str,
    k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[RegulationSearchResult]:
    """
    Recupera los k chunks normativos más relevantes para una consulta.

    Parámetros
    ----------
    query:
        Texto de la consulta en alemán (p.ej. "Mindestfläche Aufenthaltsraum").
    ollama_client:
        OllamaClient para generar el embedding de la consulta.
    qdrant_client:
        AsyncQdrantClient conectado a la instancia Qdrant.
    collection_name:
        Nombre de la colección Qdrant.
    k:
        Número máximo de resultados a devolver.
    filters:
        Filtros exactos adicionales. Claves soportadas:
        ``document`` (p.ej. "GEG"), ``section`` (p.ej. "Abschnitt 3").
        Los filtros se aplican como condiciones AND sobre el payload.

    Devuelve
    --------
    Lista de RegulationSearchResult ordenada por relevancia descendente.
    """
    # Embedding de la consulta
    embeddings = await ollama_client.embed(query)
    query_vector: list[float] = embeddings[0]

    # Construir filtro Qdrant si se especificaron campos
    qdrant_filter = _build_filter(filters) if filters else None

    # Búsqueda vectorial
    results = await qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=k,
        with_payload=True,
    )

    return [_scored_point_to_result(point) for point in results]


def _build_filter(filters: dict[str, str]) -> Any:
    """
    Construye un filtro Qdrant a partir de un dict de campos exactos.

    Ejemplo: {"document": "GEG", "section": "Abschnitt 3"}
    produce Filter(must=[FieldCondition("document", "GEG"), ...]).
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    conditions = [
        FieldCondition(key=key, match=MatchValue(value=value)) for key, value in filters.items()
    ]
    return Filter(must=conditions)


def _scored_point_to_result(point: Any) -> RegulationSearchResult:
    """Convierte un ScoredPoint de Qdrant a RegulationSearchResult."""
    payload: dict[str, Any] = point.payload or {}
    chunk = RegulationChunk(
        id=str(point.id),
        document=payload.get("document", ""),
        section=payload.get("section", "Allgemein"),
        article_number=payload.get("article_number", ""),
        article_title=payload.get("article_title", ""),
        text=payload.get("text", ""),
        metadata={k: v for k, v in payload.items() if k not in _KNOWN_PAYLOAD_KEYS},
    )
    return RegulationSearchResult(chunk=chunk, score=float(point.score))


_KNOWN_PAYLOAD_KEYS = frozenset({"document", "section", "article_number", "article_title", "text"})


def format_chunks_for_llm(results: list[RegulationSearchResult]) -> str:
    """
    Formatea los resultados de recuperación como contexto para el LLM normativo.

    Cada chunk se presenta con su referencia normativa (§ N, Dokument) para que
    el LLM pueda citar la fuente específica en su respuesta.
    """
    if not results:
        return "(Keine relevanten Normvorschriften gefunden.)"

    lines: list[str] = []
    for result in results:
        chunk = result.chunk
        ref = f"[{chunk.document} {chunk.article_number}]"
        if chunk.article_title:
            ref += f" {chunk.article_title}"
        lines.append(f"{ref}\n{chunk.text.strip()}")
        lines.append("")  # línea en blanco entre artículos

    return "\n".join(lines).strip()
