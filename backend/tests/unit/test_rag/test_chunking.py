"""Tests unitarios para el chunking por artículo de normativa alemana."""

from __future__ import annotations

import pytest

from cimiento.rag.ingestion import _clean_pdf_text, chunk_by_article
from cimiento.rag.schemas import RegulationChunk

# ---------------------------------------------------------------------------
# Texto de ejemplo: fragmento de normativa alemana sintética
# ---------------------------------------------------------------------------

SAMPLE_MBO_TEXT = """\
Musterbauordnung (MBO) — Fassung November 2016

Abschnitt 1
Allgemeine Vorschriften

§ 1 Anwendungsbereich

(1) Dieses Gesetz gilt für bauliche Anlagen und Bauprodukte.
(2) Es gilt nicht für Anlagen des öffentlichen Verkehrs.

§ 2 Begriffe

(1) Im Sinne dieses Gesetzes sind
1. Gebäude: selbstständig benutzbare, überdeckte bauliche Anlagen,
die von Menschen betreten werden können.
2. Aufenthaltsräume: Räume, die zum nicht nur vorübergehenden Aufenthalt von Menschen bestimmt
oder geeignet sind.

Abschnitt 2
Anforderungen an Gebäude

§ 35 Notwendige Treppen

(1) Jedes Gebäude mit mehr als einer Wohnung oder Nutzungseinheit muss
mindestens eine notwendige Treppe haben.
Notwendige Treppen müssen mindestens 1,00 m breit sein.

(2) Notwendige Treppen müssen ins Freie führen.

§ 37 Aufzüge

(1) In Gebäuden mit mehr als vier Vollgeschossen ist mindestens ein
Aufzug einzubauen.
"""

SAMPLE_GEG_TEXT = """\
Gebäudeenergiegesetz (GEG)
Vom 8. August 2020, zuletzt geändert am 16. Oktober 2023

§ 1 Zweck und Ziel des Gesetzes

Zweck dieses Gesetzes ist ein möglichst sparsamer Einsatz von Energie in Gebäuden
einschließlich einer zunehmenden Nutzung erneuerbarer Energien zur Erzeugung von Wärme,
Kälte und Strom für den Gebäudebetrieb.

§ 10 Anforderungen an zu errichtende Wohngebäude

(1) Ein Wohngebäude ist so zu errichten, dass der Jahres-Primärenergiebedarf
für Heizung, Warmwasserbereitung, Lüftung und Kühlung das 0,55fache des
entsprechenden Referenzgebäudes nicht überschreitet.

§ 12 Anforderungen an die Wärmedämmung

(1) Bei zu errichtenden Gebäuden darf der spezifische auf die wärmeübertragende
Umfassungsfläche bezogene Transmissionswärmeverlust H'T die in Anlage 3 festgelegten
Höchstwerte nicht überschreiten.
"""

PREAMBLE_ONLY_TEXT = """\
Vorwort

Diese Verordnung tritt am 1. Januar 2024 in Kraft.
Sie gilt für alle baulichen Anlagen im Bundesgebiet.
"""

# ---------------------------------------------------------------------------
# Tests de extracción y chunking
# ---------------------------------------------------------------------------


def test_chunk_count_mbo():
    """Se generan tantos chunks como artículos § detectados más preámbulo."""
    chunks = chunk_by_article(SAMPLE_MBO_TEXT, document="MBO")
    # Preámbulo + § 1 + § 2 + § 35 + § 37 = 5 chunks
    assert len(chunks) == 5


def test_article_numbers_extracted():
    """Los números de artículo se extraen correctamente de cada §."""
    chunks = chunk_by_article(SAMPLE_MBO_TEXT, document="MBO")
    article_numbers = [c.article_number for c in chunks if c.article_number != "Präambel"]
    assert "§ 1" in article_numbers
    assert "§ 2" in article_numbers
    assert "§ 35" in article_numbers
    assert "§ 37" in article_numbers


def test_section_tracking():
    """El Abschnitt activo se asigna correctamente a los chunks del § siguiente."""
    chunks = chunk_by_article(SAMPLE_MBO_TEXT, document="MBO")
    chunk_35 = next(c for c in chunks if c.article_number == "§ 35")
    assert "Abschnitt 2" in chunk_35.section or "Anforderungen" in chunk_35.section


def test_document_uppercased():
    """El campo document se normaliza a mayúsculas."""
    chunks = chunk_by_article(SAMPLE_MBO_TEXT, document="mbo")
    assert all(c.document == "MBO" for c in chunks)


def test_chunk_text_contains_article_body():
    """El texto del chunk contiene el cuerpo del artículo."""
    chunks = chunk_by_article(SAMPLE_GEG_TEXT, document="GEG")
    chunk_10 = next((c for c in chunks if c.article_number == "§ 10"), None)
    assert chunk_10 is not None
    assert "Primärenergiebedarf" in chunk_10.text


def test_deterministic_id():
    """El mismo documento + artículo siempre produce el mismo ID."""
    id1 = RegulationChunk.make_id("GEG", "§ 10")
    id2 = RegulationChunk.make_id("GEG", "§ 10")
    assert id1 == id2


def test_different_documents_different_ids():
    """Documentos distintos con el mismo § producen IDs distintos."""
    id_geg = RegulationChunk.make_id("GEG", "§ 1")
    id_mbo = RegulationChunk.make_id("MBO", "§ 1")
    assert id_geg != id_mbo


def test_no_articles_returns_single_chunk():
    """Un texto sin marcadores § se indexa como bloque único."""
    chunks = chunk_by_article(PREAMBLE_ONLY_TEXT, document="TEST")
    assert len(chunks) == 1
    assert chunks[0].article_number == "Präambel"


def test_geg_chunk_count():
    """El fragmento del GEG genera tres artículos."""
    chunks = chunk_by_article(SAMPLE_GEG_TEXT, document="GEG")
    article_chunks = [c for c in chunks if c.article_number != "Präambel"]
    assert len(article_chunks) == 3


def test_preamble_before_first_article():
    """El texto anterior al primer § se captura como preámbulo."""
    chunks = chunk_by_article(SAMPLE_MBO_TEXT, document="MBO")
    preamble = next((c for c in chunks if c.article_number == "Präambel"), None)
    assert preamble is not None
    assert "Musterbauordnung" in preamble.text


# ---------------------------------------------------------------------------
# Tests del limpiador de texto PDF
# ---------------------------------------------------------------------------


def test_clean_removes_page_numbers():
    text = "§ 1 Anwendungsbereich\n\n  14  \n\nDieses Gesetz gilt…"
    cleaned = _clean_pdf_text(text)
    assert "  14  " not in cleaned


def test_clean_joins_hyphenated_words():
    text = "Aufenthalts-\nräume sind Räume"
    cleaned = _clean_pdf_text(text)
    assert "Aufenthaltsräume" in cleaned


def test_clean_normalizes_multiple_blank_lines():
    text = "Absatz 1\n\n\n\nAbsatz 2"
    cleaned = _clean_pdf_text(text)
    assert "\n\n\n" not in cleaned


def test_clean_removes_bundesgesetzblatt_header():
    text = "Bundesgesetzblatt Jahrgang 2023 Teil I Nr. 42\n\n§ 1 Anwendungsbereich"
    cleaned = _clean_pdf_text(text)
    assert "Bundesgesetzblatt" not in cleaned
    assert "§ 1" in cleaned
