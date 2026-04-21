"""Capa RAG de normativa alemana de edificación (GEG, MBO, LBO)."""

from cimiento.rag.ingestion import chunk_by_article, extract_text_from_pdf, ingest_pdf
from cimiento.rag.retriever import format_chunks_for_llm, retrieve
from cimiento.rag.schemas import RegulationChunk, RegulationSearchResult

__all__ = [
    "RegulationChunk",
    "RegulationSearchResult",
    "chunk_by_article",
    "extract_text_from_pdf",
    "format_chunks_for_llm",
    "ingest_pdf",
    "retrieve",
]
