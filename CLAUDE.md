# CLAUDE.md — Guía de trabajo para Cimiento

## 1. Contexto del proyecto

Cimiento es un copiloto local de anteproyecto residencial que combina razonamiento conversacional (Ollama + LangGraph), optimización espacial (OR-Tools) y generación BIM abierta (IfcOpenShell). Funciona íntegramente en local, sin dependencias de servicios en la nube. El objetivo es asistir al arquitecto en la fase de anteproyecto: distribución de espacios, cumplimiento normativo y generación de modelo IFC.

## 2. Arquitectura en capas

El sistema se organiza en cinco capas verticales, de menor a mayor abstracción:

1. **Solver** (`src/cimiento/solver/`) — Optimización espacial con OR-Tools CP-SAT.
2. **Geometry** (`src/cimiento/geometry/`) — Operaciones geométricas puras (sin LLM).
3. **BIM** (`src/cimiento/bim/`) — Generación y lectura de archivos IFC con IfcOpenShell.
4. **API** (`src/cimiento/api/`) — Endpoints FastAPI que exponen el sistema al exterior.
5. **LLM / Agentes** (`src/cimiento/llm/`) — Razonamiento conversacional con LangGraph y Ollama.

Las capas superiores pueden invocar a las inferiores; nunca al revés.

## 3. Principios no negociables

- **El LLM nunca resuelve geometría.** Cualquier cálculo espacial o de distribución debe ir a través del solver o de la capa de geometry. El LLM interpreta y comunica; no calcula.
- **Las capas se comunican exclusivamente vía schemas Pydantic** definidos en `src/cimiento/schemas/`. Nada de dicts libres entre módulos.
- **OR-Tools CP-SAT es el solver.** No proponer ni introducir solvers alternativos (PuLP, scipy.optimize, etc.) sin discusión y decisión explícita previa.
- **IFC es el formato BIM canónico.** DXF y XLSX son formatos derivados de exportación; nunca son la fuente de verdad del modelo.

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

**Fase 4 completada. Siguiente foco: Fase 5 — copiloto conversacional sobre una base web ya usable.**

Las Fases 1 a 4 dejan ya un producto operable en local:
- Fase 1: schemas Pydantic v2, solver CP-SAT con `AddNoOverlap2D`.
- Fase 2: schemas arquitectónicos, builder `Solution→Building`, exportación IFC4/DXF/XLSX.
- Fase 3: soporte operativo de solares poligonales, comunicación vertical y mejoras geométricas clave.
- Fase 4: FastAPI + frontend React/TypeScript en alemán, generación con WebSocket, visor IFC y descargas.

Los outputs de referencia siguen en `data/outputs/rectangular_simple.*` y la API genera outputs versionados en `backend/data/outputs/api/`.

El siguiente trabajo debe concentrarse en:
1. Orquestación conversacional con LangGraph y Ollama.
2. Tool-calling validado con Pydantic hacia solver, builder y validadores.
3. UX conversacional sobre el flujo ya existente de proyectos, versiones y generación.

## 7. Qué NO hacer todavía

- No implementar RAG normativo todavía (`src/cimiento/rag/`). Eso es Fase 6.
- No implementar ingesta visual de planos (`src/cimiento/vision/`). Eso es Fase 7.
- No implementar render fotorrealista. Eso es Fase 8.
- No romper la separación de capas: el LLM puede orquestar, pero no resolver geometría.
- No añadir dependencias backend sin justificación y aprobación explícita.
