"""
Tool de consulta normativa para el agente copiloto.

Stub de Fase 5: devuelve datos mock de normativa urbanística típica española.
La implementación real (RAG sobre base de datos normativa) es Fase 6.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegulationItem(BaseModel):
    """Ítem normativo individual."""

    code: str = Field(..., description="Código de referencia normativa")
    description: str = Field(..., description="Descripción del precepto")
    value: str = Field(..., description="Valor o rango del parámetro")
    source: str = Field(..., description="Fuente normativa (norma, artículo)")


class RegulationQueryResult(BaseModel):
    """Resultado de una consulta normativa."""

    topic: str = Field(..., description="Tema consultado")
    is_mock: bool = Field(
        default=True,
        description="True mientras no esté implementado el RAG normativo (Fase 6)",
    )
    disclaimer: str = Field(
        ...,
        description=(
            "Aviso obligatorio de que los datos son aproximados y no constituyen "
            "asesoramiento jurídico ni técnico vinculante"
        ),
    )
    items: list[RegulationItem] = Field(
        default_factory=list,
        description="Ítems normativos encontrados",
    )


# ---------------------------------------------------------------------------
# Datos mock de normativa española típica (uso residencial colectivo)
# ---------------------------------------------------------------------------

_MOCK_REGULATIONS: dict[str, list[RegulationItem]] = {
    "height": [
        RegulationItem(
            code="CTE-DB-SE-AE",
            description="Número máximo de plantas sobre rasante en zona residencial plurifamiliar",
            value="Variable según planeamiento municipal; típico 3–7 plantas (9–21 m)",
            source="Plan General Municipal / Normas Subsidiarias",
        ),
        RegulationItem(
            code="NBE-FL-90",
            description="Altura libre mínima de planta habitable",
            value="≥ 2,50 m (recomendado ≥ 2,70 m)",
            source="NBE-FL-90, Art. 3",
        ),
    ],
    "coverage": [
        RegulationItem(
            code="PGOU",
            description=(
                "Ocupación máxima del solar "
                "(relación entre huella del edificio y superficie del solar)"
            ),
            value="40 %–60 % según zona; verificar PGOU municipal",
            source="Plan General de Ordenación Urbana local",
        ),
    ],
    "far": [
        RegulationItem(
            code="PGOU",
            description="Índice de edificabilidad bruta (m² construidos / m² solar)",
            value="0,5–2,5 m²/m² según uso y zona; verificar PGOU",
            source="Plan General de Ordenación Urbana local",
        ),
    ],
    "habitability": [
        RegulationItem(
            code="CTE-DB-HS-3",
            description="Superficie útil mínima de vivienda (programa completo)",
            value="≥ 38 m² útiles (estudio); ≥ 55 m² (1 dormitorio); ≥ 70 m² (2 dormitorios)",
            source="CTE DB-HS 3 / Decreto autonómico de habitabilidad",
        ),
        RegulationItem(
            code="CTE-DB-SUA",
            description="Anchura mínima de pasillos y circulaciones interiores",
            value="≥ 0,90 m pasillos; ≥ 1,20 m acceso a dormitorios",
            source="CTE DB-SUA-1",
        ),
    ],
    "parking": [
        RegulationItem(
            code="PGOU",
            description="Dotación mínima de plazas de aparcamiento en uso residencial",
            value="1 plaza / vivienda (uso privado); ratio PMR: 1 plaza accesible cada 33 estándar",
            source="Plan General Municipal / RD 1/2013 PMR",
        ),
    ],
    "accessibility": [
        RegulationItem(
            code="CTE-DB-SUA-9",
            description="Obligación de ascensor en edificios plurifamiliares",
            value="Obligatorio cuando la planta superior supera 3 alturas o 10 m de desnivel",
            source="CTE DB-SUA-9, Art. 1.1",
        ),
    ],
}

_DEFAULT_DISCLAIMER = (
    "AVISO: Estos datos son aproximaciones de la normativa española vigente para uso "
    "residencial colectivo. No constituyen asesoramiento técnico ni jurídico vinculante. "
    "Consulta el planeamiento municipal específico y las normativas autonómicas aplicables. "
    "Implementación completa prevista en Fase 6 (RAG normativo)."
)


def query_regulation(topic: str) -> RegulationQueryResult:
    """
    Consulta datos normativos sobre un tema urbanístico o de habitabilidad.

    Stub de Fase 5: devuelve datos mock de normativa española típica.
    La implementación real con RAG sobre base de datos actualizada es Fase 6.

    Parámetros
    ----------
    topic:
        Tema normativo a consultar. Valores reconocidos: ``height``, ``coverage``,
        ``far``, ``habitability``, ``parking``, ``accessibility``.
        Para temas no reconocidos devuelve todos los ítems disponibles.
    """
    normalized = topic.lower().strip()
    items = _MOCK_REGULATIONS.get(normalized) or [
        item for items in _MOCK_REGULATIONS.values() for item in items
    ]
    return RegulationQueryResult(
        topic=topic,
        is_mock=True,
        disclaimer=_DEFAULT_DISCLAIMER,
        items=items,
    )


# ---------------------------------------------------------------------------
# Definición Ollama para tool-calling
# ---------------------------------------------------------------------------

QUERY_REGULATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "query_regulation",
        "description": (
            "Consulta normativa urbanística o de habitabilidad aplicable al proyecto. "
            "Devuelve parámetros normativos (alturas, edificabilidad, ocupación, habitabilidad, "
            "aparcamiento, accesibilidad). "
            "AVISO: datos aproximados (stub); implementación RAG completa en Fase 6. "
            "Úsala cuando el arquitecto pregunte sobre límites normativos o requisitos legales."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "Tema normativo a consultar. "
                        "Valores: 'height', 'coverage', 'far', 'habitability', "
                        "'parking', 'accessibility'."
                    ),
                    "enum": [
                        "height", "coverage", "far",
                        "habitability", "parking", "accessibility",
                    ],
                }
            },
            "required": ["topic"],
        },
    },
}
