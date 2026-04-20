"""Localización simple de mensajes de error para la API pública."""

from __future__ import annotations

ERROR_MESSAGES_DE: dict[str, str] = {
    "PROJECT_NOT_FOUND": "Das Projekt wurde nicht gefunden.",
    "PROJECT_HAS_NO_VERSION": "Für dieses Projekt ist keine gespeicherte Version vorhanden.",
    "JOB_NOT_FOUND": "Der Generierungsauftrag wurde nicht gefunden.",
    "OUTPUT_NOT_FOUND": "Die angeforderte Datei wurde nicht gefunden.",
    "UNSUPPORTED_OUTPUT_FORMAT": "Das angeforderte Ausgabeformat wird nicht unterstützt.",
    "INFEASIBLE_SOLUTION": "Für die angegebenen Parameter konnte keine gültige Lösung berechnet werden.",
    "GENERATION_FAILED": "Die Generierung konnte nicht abgeschlossen werden.",
    "VALIDATION_ERROR": "Die Anfrage enthält ungültige Daten.",
    "DATABASE_UNAVAILABLE": "Die Datenbank ist derzeit nicht verfügbar.",
    "OLLAMA_UNAVAILABLE": "Ollama ist derzeit nicht erreichbar.",
    "QDRANT_UNAVAILABLE": "Qdrant ist derzeit nicht erreichbar.",
    "INTERNAL_ERROR": "Ein interner Fehler ist aufgetreten.",
}


def translate_error(code: str, **context: object) -> str:
    """Devuelve el mensaje en alemán para un código de error estándar."""
    template = ERROR_MESSAGES_DE.get(code, ERROR_MESSAGES_DE["INTERNAL_ERROR"])
    try:
        return template.format(**context)
    except Exception:  # noqa: BLE001
        return template