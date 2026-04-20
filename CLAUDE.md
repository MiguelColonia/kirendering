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

**Fase 3 — Geometría avanzada y solver con dimensiones variables.**

Las Fases 1 y 2 están completadas (92 tests pasando):
- Fase 1: schemas Pydantic v2, solver CP-SAT con `AddNoOverlap2D`.
- Fase 2: schemas arquitectónicos, builder `Solution→Building`, exportación IFC4/DXF/XLSX.

Los outputs de referencia están en `data/outputs/rectangular_simple.*` (IFC, DXF, XLSX, SVG).

El trabajo en curso en Fase 3 se centra en:
1. Geometría de solares irregulares (polígonos no rectangulares).
2. Muros diagonales y `IfcOpeningElement` con corte booleano real.
3. Solver con dimensiones variables (`AddMultiplicationEquality`).
4. Núcleos de comunicación vertical (escaleras, ascensores).

## 7. Qué NO hacer todavía

- No escribir código de LLM ni agentes (`src/cimiento/llm/`). Eso es Fase 5.
- No escribir endpoints FastAPI (`src/cimiento/api/`). Eso es Fase 4.
- No escribir frontend. No hay decisiones tomadas aún sobre la UI.
- No añadir dimensiones variables al solver hasta que la capa geometry esté lista (Fase 3).
