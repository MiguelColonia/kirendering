# Arquitectura de Cimiento

## Principio fundamental

Separación estricta en tres niveles de inteligencia:

1. **Razonamiento** (LLM): conversa, orquesta, explica. NO decide geometría.
2. **Optimización** (OR-Tools): resuelve distribución espacial bajo restricciones. Determinista.
3. **Materialización** (IfcOpenShell + Shapely): traduce solución abstracta a BIM real.

## Flujo de una petición típica

1. Usuario envía prompt en lenguaje natural.
2. LangGraph → Agente de Requisitos extrae parámetros.
3. Agente Normativo valida contra RAG normativo.
4. Agente Topológico INVOCA el solver (no resuelve él mismo).
5. OR-Tools devuelve solución o infactibilidad.
6. Agente Validador revisa; si falla, vuelve al paso 2-4.
7. Módulo BIM genera IFC/DXF/XLSX.
8. API devuelve resultado al frontend.
