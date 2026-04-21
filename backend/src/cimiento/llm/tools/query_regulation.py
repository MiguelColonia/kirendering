"""
Tool de consulta normativa para el agente normativo de Cimiento.

Fase 6: implementación real con RAG sobre Qdrant.
Si el cliente Qdrant no está disponible (desarrollo sin Qdrant activo), recae en datos
mock de normativa alemana de edificación (GEG 2023, MBO 2016) para mantener la usabilidad
del sistema completo.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from cimiento.llm.client import OllamaClient

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas de resultado (compatibles con el grafo de Fase 5)
# ---------------------------------------------------------------------------


class RegulationItem(BaseModel):
    """Ítem normativo individual devuelto por la consulta."""

    code: str = Field(..., description="Código de referencia normativa (p.ej. 'GEG § 10')")
    description: str = Field(..., description="Descripción del precepto")
    value: str = Field(..., description="Valor o rango del parámetro")
    source: str = Field(..., description="Fuente normativa (norma, artículo)")


class RegulationQueryResult(BaseModel):
    """Resultado de una consulta normativa."""

    topic: str
    is_mock: bool = Field(
        default=False,
        description="True cuando los datos son del fallback mock (sin Qdrant disponible)",
    )
    disclaimer: str
    items: list[RegulationItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Datos mock de normativa alemana de edificación
# (GEG 2023, MBO 2016, Wohnflächenverordnung WoFlV)
# Usados como fallback cuando Qdrant no está disponible
# ---------------------------------------------------------------------------

_MOCK_DE: dict[str, list[RegulationItem]] = {
    "height": [
        RegulationItem(
            code="MBO § 2 Abs. 3",
            description="Lichte Mindesthöhe von Aufenthaltsräumen",
            value="≥ 2,40 m (Dachgeschoss: mind. 2,20 m über 50% der Grundfläche)",
            source="MBO 2016, § 2 Absatz 3",
        ),
        RegulationItem(
            code="MBO § 37 Abs. 1",
            description="Pflicht zur Aufzugsanlage in Mehrfamilienhäusern",
            value=(
                "Aufzug erforderlich, wenn das Gebäude mehr als 4 Vollgeschosse hat "
                "oder der Fußboden des höchsten Geschosses mehr als 13 m über dem "
                "Erdgeschossniveau liegt"
            ),
            source="MBO 2016, § 37 Absatz 1",
        ),
    ],
    "coverage": [
        RegulationItem(
            code="BauNVO § 17",
            description="Grundflächenzahl (GRZ) im allgemeinen Wohngebiet (WA)",
            value="GRZ ≤ 0,4 im WA; bis 0,6 mit Nebenanlagen (§ 19 Abs. 4 BauNVO)",
            source="Baunutzungsverordnung (BauNVO) 2017, § 17",
        ),
    ],
    "far": [
        RegulationItem(
            code="BauNVO § 17",
            description="Geschossflächenzahl (GFZ) im allgemeinen Wohngebiet",
            value="GFZ ≤ 1,2 im WA; bis 2,0 in urbanen Gebieten (MU)",
            source="BauNVO 2017, § 17",
        ),
    ],
    "habitability": [
        RegulationItem(
            code="WoFlV § 4",
            description="Mindestfläche einer Wohnung (Wohnflächenberechnung nach WoFlV)",
            value=(
                "1-Zimmer-Wohnung: ≥ 30 m² (Wohnfläche); "
                "2-Zimmer-Wohnung: ≥ 45 m²; "
                "3-Zimmer-Wohnung: ≥ 60 m² "
                "(Landesbauordnungen können abweichen)"
            ),
            source="Wohnflächenverordnung (WoFlV), § 4; II. BV § 44",
        ),
        RegulationItem(
            code="MBO § 35 Abs. 1",
            description="Mindestbreite notwendiger Treppen",
            value="≥ 1,00 m lichte Breite; in Gebäuden mit mehr als 30 Wohnungen ≥ 1,20 m",
            source="MBO 2016, § 35 Absatz 1",
        ),
    ],
    "energy": [
        RegulationItem(
            code="GEG § 10 Abs. 2",
            description="Jahres-Primärenergiebedarf Neubau Wohngebäude",
            value="Q_P ≤ 55 kWh/(m²·a) (berechnet nach DIN V 18599)",
            source="GEG 2023, § 10 Absatz 2; Anlage 1 Tabelle 1",
        ),
        RegulationItem(
            code="GEG § 12",
            description="Spezifischer Transmissionswärmeverlust H'T",
            value=(
                "H'T ≤ 0,40 W/(m²K) für Wohngebäude; "
                "Richtwerte Außenwand U ≤ 0,24, Dach U ≤ 0,20, Fenster U ≤ 1,3 W/(m²K)"
            ),
            source="GEG 2023, § 12; Anlage 3 Tabelle 1",
        ),
    ],
    "parking": [
        RegulationItem(
            code="MBO § 47 Abs. 1",
            description="Notwendige Stellplätze für Wohngebäude",
            value=(
                "1 Stellplatz je Wohnung; bei > 6 Wohneinheiten zusätzlich "
                "Fahrradabstellplätze nach LBO"
            ),
            source="MBO 2016, § 47 Absatz 1; konkrete LBO des Bundeslandes",
        ),
    ],
    "accessibility": [
        RegulationItem(
            code="MBO § 50 Abs. 1",
            description="Barrierefreie Wohnungen in Mehrfamilienhäusern",
            value=(
                "In Gebäuden mit mehr als 2 Wohnungen müssen die Wohnungen eines "
                "Geschosses barrierefrei erreichbar sein; "
                "ab 30 Wohnungen: ≥ 10% als vollständig barrierefreie Wohnungen"
            ),
            source="MBO 2016, § 50 Absatz 1–2",
        ),
        RegulationItem(
            code="DIN 18040-2",
            description="Lichte Breite von Fluren und Türen in barrierefreien Wohnungen",
            value=(
                "Flure ≥ 1,20 m; Türen ≥ 0,90 m lichte Breite; "
                "Bewegungsfläche vor Türen ≥ 1,50 × 1,50 m"
            ),
            source="DIN 18040-2:2011 Abschnitt 4.3",
        ),
    ],
}

_MOCK_DISCLAIMER = (
    "HINWEIS: Diese Angaben sind Richtwerte aus GEG 2023, MBO 2016, BauNVO und WoFlV "
    "für Wohngebäude in Deutschland. Sie ersetzen keine verbindliche bau- und planungsrechtliche "
    "Prüfung. Landesbauordnungen (LBO) der einzelnen Bundesländer können abweichende "
    "Anforderungen stellen. Angaben ohne Gewähr."
)

_RAG_DISCLAIMER = (
    "Angaben basieren auf indizierten Normdokumenten (GEG, MBO, LBO). "
    "Für verbindliche Auskünfte ist immer die aktuelle Fassung der einschlägigen "
    "Rechtsnormen und das örtliche Baurecht maßgebend."
)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


async def query_regulation(
    query: str,
    *,
    ollama_client: OllamaClient | None = None,
    qdrant_client: Any | None = None,
    collection_name: str = "normativa",
    k: int = 5,
    document_filter: str | None = None,
) -> RegulationQueryResult:
    """
    Consulta normativa de edificación alemana mediante RAG o datos mock.

    Cuando qdrant_client es None, recurre al fallback mock (útil en desarrollo
    sin Qdrant activo y en tests unitarios del grafo).

    Parámetros
    ----------
    query:
        Consulta en alemán (p.ej. "Mindesthöhe Aufenthaltsraum MBO").
        En modo mock se mapea a temas predefinidos (height, habitability, etc.).
    ollama_client:
        OllamaClient para embeddings. Solo necesario en modo RAG.
    qdrant_client:
        AsyncQdrantClient. Si es None se usa el fallback mock.
    collection_name:
        Colección Qdrant con la normativa indexada.
    k:
        Número de chunks a recuperar.
    document_filter:
        Filtra resultados a un documento específico (p.ej. "GEG", "MBO").
    """
    if qdrant_client is None or ollama_client is None:
        return _mock_query(query)

    return await _rag_query(
        query=query,
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        k=k,
        document_filter=document_filter,
    )


async def _rag_query(
    query: str,
    ollama_client: Any,
    qdrant_client: Any,
    collection_name: str,
    k: int,
    document_filter: str | None,
) -> RegulationQueryResult:
    """Consulta real mediante búsqueda vectorial en Qdrant."""
    from cimiento.rag.retriever import retrieve

    filters: dict[str, str] | None = None
    if document_filter:
        filters = {"document": document_filter.upper()}

    try:
        results = await retrieve(
            query=query,
            ollama_client=ollama_client,
            qdrant_client=qdrant_client,
            collection_name=collection_name,
            k=k,
            filters=filters,
        )
    except Exception:
        log.exception(
            "Error en búsqueda vectorial para consulta '%s'. Recayendo en mock.", query
        )
        return _mock_query(query)

    items = [
        RegulationItem(
            code=f"{r.chunk.document} {r.chunk.article_number}".strip(),
            description=r.chunk.article_title or r.chunk.article_number,
            value=r.chunk.text[:400] + ("…" if len(r.chunk.text) > 400 else ""),
            source=f"{r.chunk.document}, {r.chunk.section}, {r.chunk.article_number}".strip(", "),
        )
        for r in results
    ]

    return RegulationQueryResult(
        topic=query,
        is_mock=False,
        disclaimer=_RAG_DISCLAIMER,
        items=items,
    )


def _mock_query(query: str) -> RegulationQueryResult:
    """Fallback mock con datos de normativa alemana de edificación."""
    normalized = query.lower().strip()
    topic_key = _map_query_to_topic(normalized)
    items = _MOCK_DE.get(topic_key) or [
        item for topic_items in _MOCK_DE.values() for item in topic_items
    ]
    return RegulationQueryResult(
        topic=query,
        is_mock=True,
        disclaimer=_MOCK_DISCLAIMER,
        items=items,
    )


def _map_query_to_topic(query_lower: str) -> str:
    """Mapea una consulta en texto libre a una clave de tema del mock."""
    keywords: dict[str, list[str]] = {
        "height": ["höhe", "geschoss", "stock", "etage", "aufzug", "fahrstuhl"],
        "coverage": ["grundfläche", "grz", "bedeckung", "bebauung"],
        "far": ["geschossfläche", "gfz", "geschossflächenzahl"],
        "habitability": ["wohnfläche", "mindestfläche", "wohnraum", "aufenthaltsraum", "treppe"],
        "energy": ["energie", "geg", "primärenergie", "wärmeschutz", "dämmung", "u-wert"],
        "parking": ["stellplatz", "garage", "parkplatz", "fahrrad"],
        "accessibility": ["barrierefrei", "behinderung", "rollstuhl", "zugänglich", "din 18040"],
    }
    for key, terms in keywords.items():
        if any(term in query_lower for term in terms):
            return key
    return "habitability"  # default


# ---------------------------------------------------------------------------
# Definición de herramienta para tool-calling Ollama
# ---------------------------------------------------------------------------

QUERY_REGULATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "query_regulation",
        "description": (
            "Sucht relevante Vorschriften aus dem deutschen Baurecht (GEG, MBO, LBO, BauNVO). "
            "Gibt Normanforderungen zu Gebäudehöhe, Grundflächenzahl, Wohnfläche, "
            "Energieeffizienz, Stellplätzen und Barrierefreiheit zurück. "
            "Verwende diese Funktion, wenn der Architekt nach gesetzlichen Anforderungen fragt."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Suchanfrage auf Deutsch, z.B. 'Mindesthöhe Aufenthaltsraum' "
                        "oder 'Primärenergiebedarf Neubau GEG'."
                    ),
                },
                "document_filter": {
                    "type": "string",
                    "description": (
                        "Optionale Einschränkung auf ein Dokument: 'GEG', 'MBO', 'LBO_Bayern'."
                    ),
                    "enum": ["GEG", "MBO", "LBO_Bayern", "LBO_NRW", "BauNVO"],
                },
            },
            "required": ["query"],
        },
    },
}
