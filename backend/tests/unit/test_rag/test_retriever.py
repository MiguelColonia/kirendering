"""Tests unitarios para el retriever vectorial de normativa alemana."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cimiento.rag.retriever import _build_filter, format_chunks_for_llm, retrieve
from cimiento.rag.schemas import RegulationChunk, RegulationSearchResult

# ---------------------------------------------------------------------------
# Helpers para construir mocks de ScoredPoint de Qdrant
# ---------------------------------------------------------------------------


def _make_scored_point(
    chunk_id: str,
    score: float,
    document: str = "GEG",
    section: str = "Abschnitt 1",
    article_number: str = "§ 10",
    article_title: str = "Anforderungen",
    text: str = "Der Jahres-Primärenergiebedarf darf 55 kWh/(m²·a) nicht überschreiten.",
) -> MagicMock:
    """Construye un mock de ScoredPoint con la estructura que devuelve Qdrant."""
    point = MagicMock()
    point.id = chunk_id
    point.score = score
    point.payload = {
        "document": document,
        "section": section,
        "article_number": article_number,
        "article_title": article_title,
        "text": text,
    }
    return point


# ---------------------------------------------------------------------------
# Tests de retrieve()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_returns_results():
    """retrieve() convierte correctamente los ScoredPoints a RegulationSearchResult."""
    fake_embedding = [[0.1] * 768]
    fake_points = [
        _make_scored_point("id-1", 0.92, article_number="§ 10"),
        _make_scored_point("id-2", 0.85, article_number="§ 12"),
    ]

    ollama_client = AsyncMock()
    ollama_client.embed.return_value = fake_embedding

    qdrant_client = AsyncMock()
    qdrant_client.search.return_value = fake_points

    results = await retrieve(
        query="Primärenergiebedarf Neubau",
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name="normativa",
        k=5,
    )

    assert len(results) == 2
    assert results[0].chunk.article_number == "§ 10"
    assert results[1].chunk.article_number == "§ 12"
    assert results[0].score == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_retrieve_passes_query_to_embed():
    """El texto de la consulta se pasa al cliente de embeddings."""
    ollama_client = AsyncMock()
    ollama_client.embed.return_value = [[0.0] * 768]
    qdrant_client = AsyncMock()
    qdrant_client.search.return_value = []

    await retrieve(
        query="Gebäudehöhe MBO",
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name="normativa",
    )

    ollama_client.embed.assert_called_once_with("Gebäudehöhe MBO")


@pytest.mark.asyncio
async def test_retrieve_passes_k_to_qdrant():
    """El parámetro k se traduce correctamente a limit de Qdrant."""
    ollama_client = AsyncMock()
    ollama_client.embed.return_value = [[0.0] * 768]
    qdrant_client = AsyncMock()
    qdrant_client.search.return_value = []

    await retrieve(
        query="test",
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name="normativa",
        k=3,
    )

    call_kwargs = qdrant_client.search.call_args.kwargs
    assert call_kwargs["limit"] == 3


@pytest.mark.asyncio
async def test_retrieve_applies_document_filter():
    """Los filtros se construyen y pasan a Qdrant cuando se especifican."""
    ollama_client = AsyncMock()
    ollama_client.embed.return_value = [[0.0] * 768]
    qdrant_client = AsyncMock()
    qdrant_client.search.return_value = []

    await retrieve(
        query="test",
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name="normativa",
        filters={"document": "GEG"},
    )

    call_kwargs = qdrant_client.search.call_args.kwargs
    assert call_kwargs["query_filter"] is not None


@pytest.mark.asyncio
async def test_retrieve_no_filter_when_none():
    """Sin filtros, query_filter es None."""
    ollama_client = AsyncMock()
    ollama_client.embed.return_value = [[0.0] * 768]
    qdrant_client = AsyncMock()
    qdrant_client.search.return_value = []

    await retrieve(
        query="test",
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name="normativa",
    )

    call_kwargs = qdrant_client.search.call_args.kwargs
    assert call_kwargs["query_filter"] is None


# ---------------------------------------------------------------------------
# Tests de _build_filter()
# ---------------------------------------------------------------------------


def test_build_filter_single_field():
    """Un filtro de un campo se construye sin excepciones."""
    from qdrant_client.models import Filter

    result = _build_filter({"document": "GEG"})
    assert isinstance(result, Filter)
    assert len(result.must) == 1


def test_build_filter_multiple_fields():
    """Un filtro de múltiples campos produce must con todas las condiciones."""
    from qdrant_client.models import Filter

    result = _build_filter({"document": "MBO", "section": "Abschnitt 2"})
    assert isinstance(result, Filter)
    assert len(result.must) == 2


# ---------------------------------------------------------------------------
# Tests de format_chunks_for_llm()
# ---------------------------------------------------------------------------


def test_format_empty_results():
    """Sin resultados devuelve el mensaje de ausencia en alemán."""
    output = format_chunks_for_llm([])
    assert "Keine" in output


def test_format_includes_reference():
    """Los resultados formateados incluyen la referencia normativa."""
    chunk = RegulationChunk(
        id=RegulationChunk.make_id("GEG", "§ 10"),
        document="GEG",
        section="Abschnitt 1",
        article_number="§ 10",
        article_title="Anforderungen an zu errichtende Wohngebäude",
        text="Der Jahres-Primärenergiebedarf darf nicht überschreiten.",
    )
    result = RegulationSearchResult(chunk=chunk, score=0.9)
    output = format_chunks_for_llm([result])

    assert "GEG" in output
    assert "§ 10" in output
    assert "Primärenergiebedarf" in output


def test_format_multiple_chunks_separated():
    """Múltiples chunks están separados por líneas en blanco."""
    chunks = [
        RegulationSearchResult(
            chunk=RegulationChunk(
                id=RegulationChunk.make_id("MBO", f"§ {n}"),
                document="MBO",
                section="Abschnitt 1",
                article_number=f"§ {n}",
                article_title=f"Artikel {n}",
                text=f"Text des Artikels {n}.",
            ),
            score=0.9,
        )
        for n in [1, 2]
    ]
    output = format_chunks_for_llm(chunks)
    assert "§ 1" in output
    assert "§ 2" in output
    # Hay al menos una línea en blanco entre los dos chunks
    assert "\n\n" in output
