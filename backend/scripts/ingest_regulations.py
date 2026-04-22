#!/usr/bin/env python
"""
Ingesta de normativa alemana de edificación en Qdrant.

Escanea data/normativa/de/ en busca de PDFs y los indexa en la colección
Qdrant configurada. Los PDFs se asocian a documentos normativos mediante
el mapa de nombres definido en DOCUMENT_MAP.

Uso:
    cd backend
    python scripts/ingest_regulations.py [opciones]

Opciones:
    --data-dir PATH         Directorio con los PDFs (por defecto: ../data/normativa/de)
    --host QDRANT_HOST      Host de Qdrant (por defecto: localhost)
    --port QDRANT_PORT      Puerto de Qdrant (por defecto: 6333)
    --collection NOMBRE     Colección Qdrant (por defecto: normativa)
    --ollama-host URL       Host de Ollama (por defecto: http://localhost:11434)
    --recreate              Elimina y recrea la colección antes de indexar
    --dry-run               Solo extrae y chunka, sin conectar a Qdrant

Ejemplo:
    # Indexar todos los PDFs disponibles
    python scripts/ingest_regulations.py

    # Solo indexar el GEG, recreando la colección
    python scripts/ingest_regulations.py --recreate

    # Comprobar el chunking sin escribir a Qdrant
    python scripts/ingest_regulations.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# El script se ejecuta desde el directorio backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cimiento.rag.ingestion import (
    chunk_by_article,
    chunk_from_gii_xml,
    extract_text_from_pdf,
    ingest_document,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de nombre de archivo → identificador de documento normativo
#
# Los identificadores determinan:
# - El campo "document" de cada RegulationChunk en Qdrant.
# - Los filtros disponibles en el retriever (document_filter="GEG", etc.).
# ---------------------------------------------------------------------------

DOCUMENT_MAP: dict[str, str] = {
    "GEG": "GEG",  # Gebäudeenergiegesetz 2023
    "MBO": "MBO",  # Musterbauordnung 2016
    "LBO_Bayern": "LBO_Bayern",  # Bayerische Bauordnung
    "LBO_BW": "LBO_BW",  # Landesbauordnung Baden-Württemberg
    "LBO_NRW": "LBO_NRW",  # Bauordnung Nordrhein-Westfalen (BauO NRW)
    "LBO_Hessen": "LBO_Hessen",  # Hessische Bauordnung (HBO)
    "BauNVO": "BauNVO",  # Baunutzungsverordnung
    "WoFlV": "WoFlV",  # Wohnflächenverordnung
    "DIN18040": "DIN18040",  # DIN 18040-2 Barrierefreies Bauen
}


def _resolve_document_id(pdf_path: Path) -> str:
    """
    Infiere el identificador de documento a partir del nombre del archivo PDF.

    Estrategia:
      1. Comprueba si alguna clave de DOCUMENT_MAP está contenida en el nombre del PDF.
      2. Si no hay coincidencia, usa el stem del nombre del archivo en mayúsculas.
    """
    stem_upper = pdf_path.stem.upper()
    for key in DOCUMENT_MAP:
        if key.upper() in stem_upper:
            return DOCUMENT_MAP[key]
    log.warning(
        "PDF '%s' no tiene una clave en DOCUMENT_MAP. Se usa '%s' como identificador.",
        pdf_path.name,
        stem_upper,
    )
    return stem_upper


async def run(
    data_dir: Path,
    qdrant_host: str,
    qdrant_port: int,
    collection_name: str,
    ollama_host: str,
    recreate: bool,
    dry_run: bool,
) -> None:
    docs = sorted(p for p in data_dir.iterdir() if p.suffix.lower() in {".pdf", ".xml"})
    if not docs:
        log.warning(
            "No se encontraron archivos PDF/XML en '%s'. "
            "Descarga los documentos normativos y colócalos en ese directorio. "
            "Consulta data/normativa/de/README.md para instrucciones.",
            data_dir,
        )
        return

    log.info("Documentos encontrados: %s", [p.name for p in docs])

    if dry_run:
        log.info("Modo dry-run: solo se procesa el chunking, sin escritura en Qdrant.")
        total_chunks = 0
        for doc_path in docs:
            doc_id = _resolve_document_id(doc_path)
            log.info("Procesando '%s' como '%s'…", doc_path.name, doc_id)
            try:
                if doc_path.suffix.lower() == ".xml":
                    chunks = chunk_from_gii_xml(doc_path, doc_id)
                    log.info("  → %d chunks generados (XML GII)", len(chunks))
                else:
                    text, meta = extract_text_from_pdf(doc_path)
                    chunks = chunk_by_article(text, document=doc_id)
                    log.info(
                        "  → %d chunks generados (%d páginas, %d caracteres)",
                        len(chunks),
                        meta.get("pages", 0),
                        len(text),
                    )
                if chunks:
                    sample = chunks[0]
                    log.info(
                        "  Primer chunk: %s '%s' (%d palabras)",
                        sample.article_number,
                        sample.article_title[:60],
                        len(sample.text.split()),
                    )
                total_chunks += len(chunks)
            except Exception:
                log.exception("Error procesando '%s'", doc_path.name)
        log.info("Dry-run completado: %d chunks totales.", total_chunks)
        return

    # Modo real: conectar a Ollama y Qdrant
    from qdrant_client import AsyncQdrantClient

    from cimiento.llm.client import OllamaClient

    ollama_client = OllamaClient(base_url=ollama_host)
    qdrant_client = AsyncQdrantClient(host=qdrant_host, port=qdrant_port)

    try:
        total_indexed = 0
        for i, doc_path in enumerate(docs):
            doc_id = _resolve_document_id(doc_path)
            log.info("[%d/%d] Indexando '%s' como '%s'…", i + 1, len(docs), doc_path.name, doc_id)
            try:
                n = await ingest_document(
                    path=doc_path,
                    document_id=doc_id,
                    ollama_client=ollama_client,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    recreate_collection=(recreate and i == 0),
                )
                total_indexed += n
                log.info("  ✓ %d chunks indexados.", n)
            except Exception:
                log.exception("Error indexando '%s'", doc_path.name)

        log.info(
            "Ingesta completada: %d chunks totales en colección '%s'.",
            total_indexed,
            collection_name,
        )
    finally:
        await ollama_client.aclose()
        await qdrant_client.close()


def main() -> None:
    default_data_dir = Path(__file__).resolve().parents[2] / "data" / "normativa" / "de"

    parser = argparse.ArgumentParser(description="Ingesta de normativa alemana en Qdrant")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    parser.add_argument("--host", default="localhost", dest="qdrant_host")
    parser.add_argument("--port", type=int, default=6333, dest="qdrant_port")
    parser.add_argument("--collection", default="normativa", dest="collection_name")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        run(
            data_dir=args.data_dir,
            qdrant_host=args.qdrant_host,
            qdrant_port=args.qdrant_port,
            collection_name=args.collection_name,
            ollama_host=args.ollama_host,
            recreate=args.recreate,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
