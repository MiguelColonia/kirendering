# CLAUDE.md — Guía de trabajo para Cimiento

## 1. Contexto del proyecto

Cimiento es un copiloto local de anteproyecto, visualización e iteración de diseño asistido por IA, desarrollado específicamente para un despacho de arquitectura especializado en infraestructuras sanitarias complejas (hospitales, clínicas y centros de investigación oncológica).

El sistema integra un motor de diseño avanzado que combina razonamiento conversacional con Ollama y LangGraph, optimización espacial determinista con OR-Tools CP-SAT, generación BIM abierta con IfcOpenShell y consulta normativa especializada a través de Qdrant.

A nivel gráfico, utiliza flujos de trabajo de generación condicional (Image-to-Image con control estructural / ControlNet) para transformar volumetrías extraídas del IFC o bocetos en renders fotorrealistas, respetando estrictamente las proporciones arquitectónicas. Además, incorpora herramientas de edición generativa interactiva (Inpainting y edición basada en instrucciones) que permiten al equipo de diseño y a los clientes iterar rápidamente sobre materiales, iluminación y distribución de fachadas o interiores clínicos directamente sobre la imagen renderizada. Todo este ecosistema está orquestado sobre una arquitectura propia de backend y frontend.


El objetivo ya no es construir el producto base, sino mantener y evolucionar una **v1.0 funcional** sin romper sus contratos arquitectónicos.

## 2. Arquitectura en capas

El sistema se organiza en siete capas verticales, de menor a mayor abstracción:

1. **Solver** (`src/cimiento/solver/`) — Optimización espacial con OR-Tools CP-SAT.
2. **Geometry** (`src/cimiento/geometry/`) — Operaciones geométricas puras (sin LLM).
3. **BIM** (`src/cimiento/bim/`) — Generación y lectura de archivos IFC con IfcOpenShell.
4. **RAG normativo** (`src/cimiento/rag/`) — Ingesta, chunking y recuperación de normativa indexada en Qdrant.
5. **Visión** (`src/cimiento/vision/`) — Ingesta visual de planos con OpenCV + VLM, siempre bajo revisión humana.
6. **API / frontend** (`src/cimiento/api/` + `frontend/`) — FastAPI, WebSockets, React + TypeScript y visor IFC.
7. **LLM / agentes** (`src/cimiento/llm/`) — Razonamiento conversacional y orquestación.

Las capas superiores pueden invocar a las inferiores; nunca al revés.

## 3. Principios no negociables

- **El LLM nunca resuelve geometría.** Todo cálculo espacial debe pasar por solver o geometry.
- **Las capas se comunican exclusivamente vía schemas Pydantic** definidos en `src/cimiento/schemas/`.
- **OR-Tools CP-SAT es el solver oficial del proyecto.**
- **IFC4 es el formato BIM canónico.** DXF, XLSX, SVG y render son derivados.
- **La salida de visión siempre requiere revisión humana** antes de alimentar al solver. Ver ADR 0012.
- **El render nunca modifica el IFC**; genera salidas visuales derivadas del modelo ya validado.
- **Los ADRs vigentes son contrato técnico.** Revisar primero `DECISIONS.md` y ADR 0015 antes de cambiar la arquitectura.

## 4. Convenciones de código

- Python 3.11+ con tipado estricto y Pydantic v2.
- Ruff como linter y formateador con `line-length = 100`.
- **Docstrings en español; código en inglés.**
- Tests con pytest. Los tests unitarios viven en `tests/unit/`; los de integración en `tests/integration/`.
- No añadir dependencias sin justificar impacto técnico y operativo.
- Metodología TDD: Al escribir nuevo código, aplica siempre la filosofía de Test-Driven Development. 
- Resolución de Bugs: Nunca modifiques el código de producción directamente para arreglar un error. Primero, escribe un test que reproduzca exactamente el bug y comprueba que falla (rojo). Solo entonces, aplica la corrección necesaria para que el test pase (verde) sin romper el resto de la suite.

## 5. Idiomas de producto y documentación

- **La UI y la salida orientada a usuario final se entregan en alemán.**
- **El mercado objetivo es Alemania**, así que términos como `Grundstück`, `Geschoss`, `Wohnprogramm` o referencias normativas alemanas no deben traducirse de forma artificial en la experiencia de producto.
- El código sigue en inglés.
- La documentación interna puede estar en español.
- La documentación de instalación y presentación al usuario se mantiene en español y alemán cuando sea útil para despliegue y adopción.

## 6. Modelos locales de referencia

- `qwen2.5:14b-instruct-q4_K_M` — razonamiento crítico.
- `qwen2.5:7b-instruct-q4_K_M` — extracción rápida y tareas ligeras.
- `qwen2.5-coder:7b-instruct-q4_K_M` — soporte de código.
- `nomic-embed-text` — embeddings del RAG normativo.
- `qwen2.5vl:7b` — interpretación visual de planos.

Los modelos efectivos y sus roles quedan fijados por los ADRs 0008, 0009 y 0013.

## 7. Hardware de referencia

Configuración validada del desarrollador original:

- CPU: AMD Ryzen 7 5700G.
- GPU: AMD Radeon RX 6600, 8 GB VRAM.
- RAM: 32 GB.
- SO: Linux.

Para render y aceleración AMD, la referencia operativa conocida usa `HSA_OVERRIDE_GFX_VERSION=10.3.0` con ROCm o fallback Vulkan según el host.

## 8. Estado actual

**v1.0 — en mantenimiento.**

Capacidades ya operativas al cierre:

- Fases 1 a 8 completadas.
- Producto web usable de extremo a extremo.
- Copiloto conversacional en alemán.
- RAG normativo local.
- Ingesta visual de planos bajo revisión humana.
- Render de proyecto con galería y descarga HQ.

Documentos de entrada para mantenimiento:

1. `README.md`
2. `docs/installation/README.md`
3. `docs/architecture/README.md`
4. `DECISIONS.md` y ADR 0015
5. `docs/progress/fase-04.md` a `docs/progress/fase-08.md`

## 9. Fases del proyecto

- [x] **Fase 1**: Solver aislado.
- [x] **Fase 2**: Geometría y exportación BIM.
- [x] **Fase 3**: Complejidad real sobre solares y núcleos.
- [x] **Fase 4**: Web básica con FastAPI + frontend + visor IFC.
- [x] **Fase 5**: Copiloto conversacional con LangGraph y Ollama.
- [x] **Fase 6**: RAG normativo local sobre Qdrant.
- [x] **Fase 7**: Ingesta visual con OpenCV + VLM.
- [x] **Fase 8**: Render fotorrealista y galería de renders.

## 10. Mantenimiento

### Reporte de bugs

No hay tracker externo por ahora. El proceso interno es:

1. Reproducir el problema en la menor superficie posible.
2. Registrar versión, hardware, SO, pasos exactos, resultado esperado y resultado real.
3. Adjuntar logs, prompt, archivo IFC o imagen de entrada si aplica.
4. Convertir el bug en test reproducible o, si no es posible aún, en una nota interna ligada al siguiente cambio de mantenimiento.

### Propuesta de nuevas features

La regla es **ADR primero, implementación después** cuando la propuesta cambie arquitectura, dependencias, política técnica o contratos entre capas.

Si la idea es solo una mejora local de UX o una ampliación pequeña sin impacto sistémico, no hace falta ADR, pero sí justificar el alcance y mantener el cambio acotado.

### Política de dependencias

- Revisión trimestral de dependencias backend y frontend.
- Antes de saltar a una major version, evaluar compatibilidad, coste de migración y riesgo operativo.
- Cualquier cambio de dependencia que altere contratos de arquitectura, pipeline de modelos o despliegue debe documentarse con ADR o, como mínimo, con una nota explícita en el cambio.

### Política de tests

Cobertura mínima aceptable por módulo:

- `solver`, `geometry`, `bim`, `rag`, `vision`, `render`: **80 %** mínimo.
- `api`, `llm`, `frontend`: **70 %** mínimo, complementado con tests de integración sobre flujos críticos.
- Todo flujo crítico de producto debe conservar al menos una validación de integración o end-to-end reproducible.

Si un cambio baja de esos umbrales, debe justificarse explícitamente y dejar plan de recuperación.

### Cómo retomar el proyecto tras un parón

Orden de lectura recomendado:

1. `README.md`
2. `docs/installation/README.md`
3. `docs/architecture/README.md`
4. `DECISIONS.md`
5. `docs/decisions/0015-cierre-v1-0-estado-de-decisiones-acumuladas.md`
6. `docs/progress/fase-04.md` a `docs/progress/fase-08.md`
7. Este `CLAUDE.md`
8. El módulo concreto que vaya a tocarse

## 11. Comandos frecuentes

```bash
# Tests backend
cd backend && pytest

# Cobertura backend
cd backend && pytest --cov=cimiento

# Lint y formato backend
cd backend && ruff check .
cd backend && ruff format .

# Build frontend
cd frontend && npm run build

# Infra de desarrollo
cd infra/docker && docker compose up --build -d

# Infra de produccion
cd infra/docker && docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

## 12. Qué no romper en mantenimiento

- No mover geometría al LLM.
- No sustituir CP-SAT sin ADR.
- No degradar IFC a formato secundario.
- No eliminar la revisión humana obligatoria en visión.
- No introducir rutas de render que rehagan el modelo fuera del IFC.
- No abrir nuevas dependencias de infraestructura sin documentar su coste operativo.
