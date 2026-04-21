# CLAUDE.md — Guía de trabajo para Cimiento

## 1. Contexto del proyecto

Cimiento es un copiloto local de anteproyecto residencial que combina razonamiento conversacional (Ollama + LangGraph), optimización espacial (OR-Tools) y generación BIM abierta (IfcOpenShell). Funciona íntegramente en local, sin dependencias de servicios en la nube. El objetivo es asistir al arquitecto en la fase de anteproyecto: distribución de espacios, cumplimiento normativo y generación de modelo IFC.

## 2. Arquitectura en capas

El sistema se organiza en siete capas verticales, de menor a mayor abstracción:

1. **Solver** (`src/cimiento/solver/`) — Optimización espacial con OR-Tools CP-SAT.
2. **Geometry** (`src/cimiento/geometry/`) — Operaciones geométricas puras (sin LLM).
3. **BIM** (`src/cimiento/bim/`) — Generación y lectura de archivos IFC con IfcOpenShell.
4. **RAG normativo** (`src/cimiento/rag/`) — Ingesta, chunking y recuperación de normativa indexada en Qdrant.
5. **Visión** (`src/cimiento/vision/`) — Ingesta visual de planos: OpenCV para geometría, VLM (qwen2.5vl:7b) para semántica. El output siempre es `PlanInterpretation` con `review_required=True`; **nunca se alimenta directamente al solver sin confirmación del usuario**.
6. **API** (`src/cimiento/api/`) — Endpoints FastAPI que exponen el sistema al exterior.
7. **LLM / Agentes** (`src/cimiento/llm/`) — Razonamiento conversacional con LangGraph y Ollama.

Las capas superiores pueden invocar a las inferiores; nunca al revés.

## 3. Principios no negociables

- **El LLM nunca resuelve geometría.** Cualquier cálculo espacial o de distribución debe ir a través del solver o de la capa de geometry. El LLM interpreta y comunica; no calcula.
- **Las capas se comunican exclusivamente vía schemas Pydantic** definidos en `src/cimiento/schemas/`. Nada de dicts libres entre módulos.
- **OR-Tools CP-SAT es el solver.** No proponer ni introducir solvers alternativos (PuLP, scipy.optimize, etc.) sin discusión y decisión explícita previa.
- **IFC es el formato BIM canónico.** DXF y XLSX son formatos derivados de exportación; nunca son la fuente de verdad del modelo.
- **El output de visión siempre requiere revisión humana.** `PlanInterpretation.draft_building` no puede usarse como entrada directa del solver. `review_required=True` es una invariante permanente, no una advertencia blanda. (ADR 0012)

## 4. Convenciones de código

- Python 3.11+. Tipado estricto: todas las funciones públicas tienen anotaciones de tipo completas. Modelos de datos con Pydantic v2.
- Linter: Ruff con `line-length = 100`. El código debe pasar `ruff check` sin advertencias antes de cualquier commit.
- **Docstrings en español; código en inglés.** Los nombres de variables, funciones, clases y módulos van en inglés. Los docstrings y comentarios explicativos van en español.
- Tests con pytest. Un test por cada función pública, mínimo. Los tests unitarios viven en `tests/unit/`; los de integración en `tests/integration/`.

## 5. Comandos frecuentes

```
# Ejecutar tests
cd backend && pytest

# Lint
cd backend && ruff check .

# Formato
cd backend && ruff format .
```

## 6. Estado actual

**Fase 7 completada. Siguiente foco: Fase 8 — render fotorrealista.**

Las Fases 1 a 7 dejan un producto con copiloto conversacional, RAG normativo e ingesta visual de planos, todo operativo en local:
- Fase 1: schemas Pydantic v2, solver CP-SAT con `AddNoOverlap2D`.
- Fase 2: schemas arquitectónicos, builder `Solution→Building`, exportación IFC4/DXF/XLSX.
- Fase 3: soporte operativo de solares poligonales, comunicación vertical y mejoras geométricas clave.
- Fase 4: FastAPI + frontend React/TypeScript en alemán, generación con WebSocket, visor IFC y descargas.
- Fase 5: LangGraph `StateGraph` de 5 nodos, OllamaClient async, UI de chat con streaming y panel lateral.
- Fase 6: RAG local sobre Qdrant con `nomic-embed-text`, chunking por artículo (§), ingesta PDF/XML y nodo `answer_with_regulation` con citas `[DOC §N]`.
- Fase 7: capa de visión (`src/cimiento/vision/`) con pipeline OpenCV + VLM (qwen2.5vl:7b): rectificación, detección de muros (HoughLinesP), lectura de etiquetas alemanas, clasificación funcional de estancias, estimación de escala y `PlanInterpretation` con `draft_building` opcional. 28 tests unitarios. (ADR 0012, ADR 0013)

Los outputs de referencia siguen en `data/outputs/rectangular_simple.*` y la API genera outputs versionados en `backend/data/outputs/api/`.

El grafo de agentes vive en `src/cimiento/llm/graphs/design_assistant.py`. Los endpoints de chat son `POST /api/projects/{id}/chat` y `WS /api/projects/{id}/chat/stream`. La UI de chat es `frontend/src/features/chat/ChatPanel.tsx`.

La normativa indexable se gestiona desde `src/cimiento/rag/` y el script de ingesta está en `backend/scripts/ingest_regulations.py`. Cuando existe XML GII se prioriza frente a PDF; la unidad primaria de chunking es el artículo completo y solo se subdivide por `Absatz` si el tamaño lo exige.

La capa de visión vive en `src/cimiento/vision/`. Su función pública principal es `combine_preprocessing_and_vlm(image_path, vlm_client)`, que devuelve un `PlanInterpretation`. La escala métrica se solicita al VLM; sin escala, `draft_building` es `None`. El modelo VLM esperado es `qwen2.5vl:7b` vía Ollama con rol `"vision"`.

## 7. Qué NO hacer todavía

- No implementar render fotorrealista. Eso es Fase 8.
- No alimentar `PlanInterpretation.draft_building` directamente al solver sin confirmación explícita del usuario. Es una invariante, no un consejo.
- No romper la separación de capas: el LLM puede orquestar, pero no resolver geometría.
- No añadir dependencias backend sin justificación y aprobación explícita.
- No sustituir el chunking por artículo del RAG por ventanas fijas sin un ADR explícito.
- No cambiar el checkpointer de `MemorySaver` a una implementación persistente sin decidir antes el esquema de base de datos y la estrategia operativa.
- No exponer la capa de visión en un endpoint API hasta diseñar el flujo de revisión humana del `draft_building` (confirmación + corrección + ingreso al solver).
