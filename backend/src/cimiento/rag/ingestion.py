"""
Pipeline de ingesta de normativa alemana de edificación en Qdrant.

Flujo:
  PDF → extracción de texto (pdfplumber) → chunking por artículo → embeddings → upsert Qdrant

Decisión de diseño — por qué chunking por artículo (§) y no ventanas fijas:
─────────────────────────────────────────────────────────────────────────────
Las normas alemanas de edificación (GEG, MBO, LBO) están estructuradas en artículos
numerados (§ N) que son unidades jurídicas completas y autocontenidas.

Ventanas fijas de tokens (p.ej. 512 tokens con solapamiento del 20%):
  • Parten un § a mitad del texto, separando los Absätze (1), (2), (3) que se referencian
    entre sí mediante "gemäß Absatz 2" o "nach Satz 1".
  • El solapamiento reproduce texto pero no restaura el contexto jurídico: el razonador
    normativo (LLM) recibe un fragmento sin saber cuál era la obligación del Absatz anterior.
  • Multiplica el número de chunks y el coste de embedding sin mejorar la recuperación.

Chunking por artículo:
  • § 14 GEG "Mindestanforderungen an Außenbauteile" es una pregunta-respuesta completa:
    el inciso inicial, las excepciones y las referencias cruzadas están en el mismo chunk.
  • nomic-embed-text soporta hasta 8 192 tokens de contexto; incluso los artículos más
    extensos del GEG (~600 palabras) caben sin truncar.
  • Permite filtrado exacto por número de artículo cuando la consulta lo referencia
    directamente, sin necesidad de búsqueda vectorial.
  • Si un artículo supera el límite práctico (~1 200 tokens), se divide por Absatz,
    que son la segunda unidad semántica natural de la norma alemana.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from cimiento.rag.schemas import RegulationChunk

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes y patrones regex para normativa alemana
# ---------------------------------------------------------------------------

# Límite práctico de tokens por chunk antes de dividir por Absatz.
# nomic-embed-text admite 8 192 tokens, pero chunks > 1 200 palabras tienden a
# diluir la señal semántica del embedding; el modelo de embedding satura.
_MAX_WORDS_PER_CHUNK = 1_200

# Patrón de artículo: línea que comienza con "§ N" o "§ Na" (p.ej. § 14a).
# Ancla al comienzo de línea para evitar falsos positivos en referencias inline como
# "gemäß § 14 Abs. 2".
_ARTICLE_RE = re.compile(r"(?m)^[ \t]*(§[ \t]*\d+[a-zA-Z]?)[ \t]*(.*?)[ \t]*$")

# Patrón de sección estructural: Abschnitt, Teil, Kapitel, Anhang, Anlage.
_SECTION_RE = re.compile(
    r"(?m)^[ \t]*((?:Abschnitt|Teil|Kapitel|Anhang|Anlage)[ \t]+\d+[a-zA-Z]?)[ \t]*(.*?)[ \t]*$",
    re.IGNORECASE,
)

# Patrón de Absatz: "(1)", "(2)", etc.  Usado para subdivisión de artículos largos.
_ABSATZ_RE = re.compile(r"(?m)^[ \t]*\((\d+)\)[ \t]+")

# Líneas que son solo números de página (estilo "— 14 —" o simplemente "14")
_PAGE_NUM_RE = re.compile(r"(?m)^[ \t]*[-–]?[ \t]*\d{1,4}[ \t]*[-–]?[ \t]*$")

# Cabeceras típicas del Bundesgesetzblatt / diarios oficiales alemanes
_HEADER_RE = re.compile(
    r"(?m)^.{0,60}(?:Bundesgesetzblatt|BGBl\.?|Drucksache|Bundesrat|Bundesanzeiger).{0,60}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Extracción de texto de PDF
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, dict[str, Any]]:
    """
    Extrae y limpia el texto completo de un PDF normativo alemán con pdfplumber.

    Por qué pdfplumber y no pypdf:
    - pdfplumber preserva la separación espacial entre columnas y tablas de valores
      (p.ej. las tablas de U-Werte del GEG Anlage 5).
    - pypdf puede concatenar palabras sin espacio cuando la codificación CID del PDF
      no incluye mapa de caracteres estándar, que es frecuente en PDFs oficiales alemanes.
    - El coste computacional adicional de pdfplumber es irrelevante en un pipeline offline.

    Parámetros
    ----------
    pdf_path:
        Ruta al archivo PDF.

    Devuelve
    --------
    Tupla (texto_limpio, metadatos) con el texto extraído y número de páginas.
    """
    try:
        import pdfplumber  # importación diferida; no requerida en tiempo de import del módulo
    except ImportError as exc:
        raise ImportError(
            "pdfplumber es necesario para la ingesta de PDFs. Instálalo con: pip install pdfplumber"
        ) from exc

    parts: list[str] = []
    metadata: dict[str, Any] = {"source_file": str(pdf_path), "pages": 0}

    with pdfplumber.open(pdf_path) as pdf:
        metadata["pages"] = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if text:
                parts.append(text)

    raw = "\n".join(parts)
    cleaned = _clean_pdf_text(raw)
    return cleaned, metadata


def _clean_pdf_text(text: str) -> str:
    """Elimina artefactos comunes de PDFs normativos alemanes."""
    text = _PAGE_NUM_RE.sub("", text)
    text = _HEADER_RE.sub("", text)
    # Reunir palabras partidas con guión al final de línea
    text = re.sub(r"-\n[ \t]*", "", text)
    # Normalizar espacios múltiples (preservar saltos de línea)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Colapsar más de dos líneas en blanco
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking por artículo
# ---------------------------------------------------------------------------


def chunk_by_article(
    full_text: str,
    document: str,
    default_section: str = "Allgemein",
) -> list[RegulationChunk]:
    """
    Divide el texto de una norma alemana en chunks por artículo (§).

    Estrategia:
      1. Detectar líneas que marcan un nuevo § con su título.
      2. El texto entre dos marcadores § consecutivos es el cuerpo del artículo.
      3. Rastrear el Abschnitt/Teil activo para contextualizar cada chunk.
      4. Si el cuerpo supera _MAX_WORDS_PER_CHUNK, dividir por Absatz (1), (2), …

    El texto anterior al primer § se trata como preámbulo (Präambel) del documento.

    Parámetros
    ----------
    full_text:
        Texto extraído del PDF ya limpio.
    document:
        Identificador del documento normativo (p.ej. "GEG", "MBO").
    default_section:
        Sección por defecto cuando no se ha encontrado ningún Abschnitt todavía.

    Devuelve
    --------
    Lista de RegulationChunk ordenada por aparición en el documento.
    """
    chunks: list[RegulationChunk] = []
    current_section = default_section

    # --- Localizar todos los marcadores § y de sección en el texto ---

    # Cada elemento: (start_pos, kind, number, title)
    # kind: "article" | "section"
    markers: list[tuple[int, str, str, str]] = []

    for match in _ARTICLE_RE.finditer(full_text):
        number = match.group(1).strip()
        title = match.group(2).strip()
        markers.append((match.start(), "article", number, title))

    for match in _SECTION_RE.finditer(full_text):
        number = match.group(1).strip()
        title = match.group(2).strip()
        markers.append((match.start(), "section", number, title))

    if not markers:
        # El documento no tiene marcadores §: indexar como bloque único
        log.warning(
            "No se encontraron marcadores § en '%s'. Se indexa como bloque único.", document
        )
        chunk = _make_chunk(document, default_section, "Präambel", "", full_text, {})
        return [chunk] if chunk.text.strip() else []

    # Ordenar por posición en el texto
    markers.sort(key=lambda m: m[0])

    # Preámbulo: texto antes del primer marcador
    preamble = full_text[: markers[0][0]].strip()
    if preamble:
        chunks.append(_make_chunk(document, default_section, "Präambel", "Präambel", preamble, {}))

    # Procesar cada marcador
    for i, (pos, kind, number, title) in enumerate(markers):
        next_pos = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)
        body = full_text[pos:next_pos].strip()

        if kind == "section":
            current_section = f"{number} {title}".strip()
            continue  # Las secciones no generan chunks propios; contextualizan a los §

        # kind == "article"
        article_chunks = _split_article_if_needed(
            document=document,
            section=current_section,
            article_number=number,
            article_title=title,
            body=body,
        )
        chunks.extend(article_chunks)

    return chunks


def _split_article_if_needed(
    *,
    document: str,
    section: str,
    article_number: str,
    article_title: str,
    body: str,
) -> list[RegulationChunk]:
    """
    Divide un artículo por Absatz si supera _MAX_WORDS_PER_CHUNK.

    La segunda unidad semántica natural de la norma alemana es el Absatz (1), (2), …
    Solo se usa como fallback cuando el § completo es demasiado largo para un embedding
    de alta calidad. La preferencia siempre es mantener el § entero.
    """
    word_count = len(body.split())
    if word_count <= _MAX_WORDS_PER_CHUNK:
        chunk = _make_chunk(document, section, article_number, article_title, body, {})
        return [chunk] if chunk.text.strip() else []

    # El § es demasiado largo: dividir por Absatz
    absatz_positions = [m.start() for m in _ABSATZ_RE.finditer(body)]
    if len(absatz_positions) <= 1:
        # Sin Absätze detectables: mantener el § entero aunque sea largo
        log.debug(
            "Artículo %s de %s supera %d palabras pero no tiene Absätze; se mantiene entero.",
            article_number,
            document,
            _MAX_WORDS_PER_CHUNK,
        )
        chunk = _make_chunk(document, section, article_number, article_title, body, {})
        return [chunk] if chunk.text.strip() else []

    parts: list[RegulationChunk] = []
    for j, start in enumerate(absatz_positions):
        end = absatz_positions[j + 1] if j + 1 < len(absatz_positions) else len(body)
        part_text = body[start:end].strip()
        if not part_text:
            continue
        chunk = _make_chunk(
            document,
            section,
            article_number,
            article_title,
            part_text,
            {"part": j + 1},
            part=j,
        )
        parts.append(chunk)
    return parts


def _make_chunk(
    document: str,
    section: str,
    article_number: str,
    article_title: str,
    text: str,
    extra_meta: dict[str, Any],
    part: int = 0,
) -> RegulationChunk:
    """Construye un RegulationChunk con ID determinista."""
    return RegulationChunk(
        id=RegulationChunk.make_id(document, article_number, part),
        document=document.upper(),
        section=section,
        article_number=article_number,
        article_title=article_title,
        text=text,
        metadata=extra_meta,
    )


# ---------------------------------------------------------------------------
# Parser XML GII (Gesetze im Internet)
# ---------------------------------------------------------------------------


def chunk_from_gii_xml(xml_path: Path, document: str) -> list[RegulationChunk]:
    """
    Parsea un XML en formato GII (Gesetze im Internet) y genera chunks por artículo.

    El formato GII estructura cada norma en un elemento <norm> con:
    - <metadaten><enbez> → número de artículo (§ N, Anlage N)
    - <metadaten><titel> → título del artículo
    - <textdaten><text><Content><P> → párrafos del texto

    Los elementos sin <enbez> (marcadores de parte/sección como "Erster Teil") y el
    elemento "Inhaltsübersicht" (índice) se omiten: no contienen contenido normativo útil.
    Las secciones con enbez pero sin texto también se omiten.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()
    chunks: list[RegulationChunk] = []
    current_section = "Allgemein"

    for norm in root.findall("norm"):
        enbez = (norm.findtext("metadaten/enbez") or "").strip()
        titel = (norm.findtext("metadaten/titel") or "").strip()

        if not enbez or enbez == "Inhaltsübersicht":
            continue

        content_elem = norm.find(".//Content")
        text = _extract_gii_text(content_elem) if content_elem is not None else ""
        if not text.strip():
            continue

        chunks.append(
            RegulationChunk(
                id=RegulationChunk.make_id(document, enbez),
                document=document.upper(),
                section=current_section,
                article_number=enbez,
                article_title=titel,
                text=text,
                metadata={},
            )
        )

    log.info(
        "XML '%s': %d chunks generados de documento '%s'.",
        xml_path.name,
        len(chunks),
        document,
    )
    return chunks


def _extract_gii_text(content_elem: Any) -> str:
    """Extrae texto limpio de un elemento <Content> GII, uniendo párrafos <P> con saltos."""
    import xml.etree.ElementTree as ET

    paragraphs = content_elem.findall(".//P")
    if paragraphs:
        return "\n".join(
            ET.tostring(p, encoding="unicode", method="text").strip() for p in paragraphs
        )
    return ET.tostring(content_elem, encoding="unicode", method="text").strip()


# ---------------------------------------------------------------------------
# Ingesta completa: PDF → Qdrant / XML → Qdrant
# ---------------------------------------------------------------------------

_EMBED_BATCH_SIZE = 32  # Chunks por batch de embedding para no saturar Ollama


async def _upsert_chunks(
    chunks: list[RegulationChunk],
    ollama_client: Any,
    qdrant_client: Any,
    collection_name: str,
) -> int:
    """Genera embeddings en batches y hace upsert en Qdrant. Devuelve el total indexado."""
    from qdrant_client.models import PointStruct

    total_upserted = 0
    for batch_start in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
        texts = [c.text for c in batch]
        embeddings: list[list[float]] = await ollama_client.embed(texts)

        points = [
            PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "document": chunk.document,
                    "section": chunk.section,
                    "article_number": chunk.article_number,
                    "article_title": chunk.article_title,
                    "text": chunk.text,
                    **{
                        k: v
                        for k, v in chunk.metadata.items()
                        if isinstance(v, (str, int, float, bool))
                    },
                },
            )
            for chunk, embedding in zip(batch, embeddings, strict=True)
        ]
        await qdrant_client.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        log.debug(
            "Batch %d–%d indexado (%d chunks)",
            batch_start + 1,
            batch_start + len(batch),
            len(points),
        )

    return total_upserted


async def ingest_document(
    path: Path,
    document_id: str,
    ollama_client: Any,
    qdrant_client: Any,
    collection_name: str,
    *,
    recreate_collection: bool = False,
) -> int:
    """
    Ingesta un documento normativo (PDF o XML GII) en Qdrant.

    Enruta automáticamente a `ingest_pdf` para .pdf o `chunk_from_gii_xml` para .xml.
    """
    log.info("Iniciando ingesta de '%s' como documento '%s'", path.name, document_id)
    await _ensure_collection(qdrant_client, collection_name, recreate=recreate_collection)

    if path.suffix.lower() == ".xml":
        chunks = chunk_from_gii_xml(path, document_id)
    else:
        text, pdf_meta = extract_text_from_pdf(path)
        log.info(
            "Texto extraído de '%s': %d páginas, %d caracteres",
            path.name,
            pdf_meta.get("pages", 0),
            len(text),
        )
        chunks = chunk_by_article(text, document=document_id)

    if not chunks:
        log.warning("No se generaron chunks para '%s'. Verifica el formato del archivo.", path.name)
        return 0

    log.info("Chunks generados: %d artículos de '%s'", len(chunks), document_id)
    total = await _upsert_chunks(chunks, ollama_client, qdrant_client, collection_name)
    log.info(
        "Ingesta completada: %d chunks de '%s' en colección '%s'",
        total,
        document_id,
        collection_name,
    )
    return total


async def ingest_pdf(
    pdf_path: Path,
    document_id: str,
    ollama_client: Any,
    qdrant_client: Any,
    collection_name: str,
    *,
    recreate_collection: bool = False,
) -> int:
    """Ingesta un PDF normativo alemán en Qdrant. Alias de ingest_document para PDFs."""
    return await ingest_document(
        pdf_path,
        document_id,
        ollama_client,
        qdrant_client,
        collection_name,
        recreate_collection=recreate_collection,
    )


async def _ensure_collection(
    qdrant_client: Any,
    collection_name: str,
    *,
    recreate: bool = False,
    vector_size: int = 768,
) -> None:
    """
    Crea la colección Qdrant si no existe; la recrea si recreate=True.

    El tamaño de vector 768 corresponde al modelo nomic-embed-text v1.5.
    La distancia coseno es estándar para embeddings de texto con normalización L2.
    """
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in (await qdrant_client.get_collections()).collections}

    if recreate and collection_name in existing:
        await qdrant_client.delete_collection(collection_name)
        existing.discard(collection_name)
        log.info("Colección '%s' eliminada para re-indexación limpia.", collection_name)

    if collection_name not in existing:
        await qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        log.info("Colección '%s' creada (dim=%d, distancia=coseno).", collection_name, vector_size)
