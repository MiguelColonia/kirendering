# CLAUDE.md

Guía operativa para Claude Code en el proyecto Cimiento. Este archivo se lee automáticamente al iniciar cada sesión.

## Contexto del proyecto

Cimiento es un copiloto local de anteproyecto residencial que combina razonamiento conversacional (Ollama + LangGraph), optimización espacial con restricciones (OR-Tools CP-SAT), generación BIM abierta (IfcOpenShell) y visualización fotorrealista (Stable Diffusion + Blender). Todo se ejecuta en local, sin enviar datos a la nube. Inspirado en Architechtures pero privado, acotado a normativa concreta y bajo control del usuario.

El producto permite además dos flujos de entrada/salida visual:
- **Ingesta de planos**: subir una foto JPG/PNG de un plano o croquis 2D y convertirlo en geometría base interpretable por el solver.
- **Render fotorrealista con referencia**: generar un render final del BIM diseñado, opcionalmente condicionado por una imagen de referencia estética subida por el usuario.

## Arquitectura en capas

El proyecto se estructura en siete capas con separación estricta de responsabilidades. Cada capa vive en su propio módulo dentro de `backend/src/cimiento/` y se comunica con las demás exclusivamente mediante schemas Pydantic.

- **Capa 0 — Ingesta visual** (`vision/`): interpretación de planos 2D desde imágenes. Modelos de visión (VLM) más OpenCV para extraer geometría de croquis y planos escaneados. Output: schema de geometría base que alimenta al solver.
- **Capa 1 — LLM y orquestación** (`llm/`): agentes conversacionales con LangGraph y Ollama. Razona, conversa, valida. No calcula geometría.
- **Capa 2 — Solver** (`solver/`): optimización espacial determinista con OR-Tools CP-SAT. Recibe parámetros, devuelve solución abstracta.
- **Capa 3 — Geometría y BIM** (`geometry/`, `bim/`): traduce la solución abstracta a geometría real y al modelo IFC canónico. DXF y XLSX son derivados del IFC.
- **Capa 4 — RAG normativo** (`rag/`): indexa y consulta normativa local mediante Qdrant y embeddings de Ollama.
- **Capa 5 — API y frontend** (`api/` + `frontend/`): FastAPI con WebSockets y React + TypeScript + IFC.js como visor BIM navegable.
- **Capa 6 — Visualización fotorrealista** (`render/`): pipeline Blender headless + Stable Diffusion con ControlNet para generar renders de presentación a partir del modelo IFC, opcionalmente condicionados por una imagen de referencia estética.

Los schemas compartidos viven en `backend/src/cimiento/schemas/` y actúan como contrato entre capas.

## Principios no negociables

- El LLM NUNCA resuelve geometría ni optimización. Siempre invoca el solver a través de una tool.
- Las capas se comunican exclusivamente vía schemas Pydantic. Prohibido pasar dicts sueltos entre capas.
- OR-Tools CP-SAT es el solver del proyecto. No proponer alternativas sin redactar un ADR en `docs/decisions/`.
- **IFC es la columna vertebral semántica del proyecto, no solo un formato de exportación.** El modelo IFC conserva la semántica (muro exterior, ventana, forjado, zona común, unidad residencial) desde el solver hasta el render final. Cualquier pipeline posterior (DXF, XLSX, render fotorrealista) deriva de ese IFC, no lo reconstruye desde cero.
- IfcOpenShell es la librería canónica para manipular IFC. Versión IFC objetivo: IFC4 (y evaluar IFC4.3 cuando el ecosistema lo permita).
- La ingesta visual (Capa 0) nunca produce directamente un IFC final. Produce una geometría base aproximada que el solver usa como restricción o punto de partida; el usuario siempre revisa y confirma antes de consolidar.
- El render fotorrealista (Capa 6) nunca altera el modelo IFC. Renderiza a partir de él, no lo modifica.
- Todo tool-calling se valida con Pydantic antes de ejecutar la herramienta. Si el LLM devuelve JSON inválido, se reintenta o falla, nunca se ejecuta con datos corruptos.
- Ningún agente LLM tiene acceso directo al sistema de archivos ni a ejecutar código arbitrario.

## Convenciones de código

- Python 3.11 o superior con tipado estricto. Pydantic v2 para todos los modelos de datos.
- Ruff para linting y formato. Line-length 100. Configuración en `backend/pyproject.toml`.
- Docstrings en español. Identificadores (funciones, variables, clases) en inglés.
- Tests con pytest. Antes de escribir una función pública, escribir el test que la describe (TDD).
- Un commit por tarea verificable. Mensajes de commit en español, estilo convencional (feat:, fix:, docs:, refactor:, test:, chore:).
- No añadir dependencias sin justificación explícita y aprobación del usuario.

## Modelos LLM y de visión locales (Ollama)

Modelos de lenguaje:

- `qwen2.5:14b-instruct-q4_K_M` — razonamiento multi-paso complejo. Usar en Agente Normativo, Agente Validador, Agente Planificador. Lento (~5-8 t/s) pero de mayor calidad.
- `qwen2.5:7b-instruct-q4_K_M` — extracción de parámetros y tareas simples. Rápido (~25-35 t/s).
- `qwen2.5-coder:7b-instruct-q4_K_M` — generación y manipulación de código.
- `nomic-embed-text` — embeddings para el RAG normativo. 768 dimensiones.

Modelos de visión (pendientes de descargar en Fase 7):

- `qwen2.5vl:7b` o equivalente — interpretación de planos 2D en la Capa 0. Decisión final de modelo concreto se tomará al iniciar la Fase 7 tras benchmark local.

Regla: al implementar un agente, elegir el modelo más pequeño que cumpla la tarea con fiabilidad. El 14B se reserva para razonamiento crítico.

## Pipeline de visualización fotorrealista (fuera de Ollama)

La Capa 6 no usa Ollama. Usa un pipeline separado:

- **Blender** en modo headless con script Python (bpy) para generar pases geométricos base a partir del IFC vía IfcOpenShell.
- **Stable Diffusion XL** o **SDXL Turbo** con **ControlNet** (depth, canny, mlsd) para condicionar la generación a la geometría del BIM.
- Frontend del render: **ComfyUI** en modo API (servicio aparte) es la opción preferida por su flexibilidad de grafos.
- Aceleración AMD vía **ROCm** o fallback DirectML/Vulkan. Evaluar rendimiento real en Fase 8 antes de decidir stack definitivo.
- El tiempo objetivo por render de presentación es 1-2 minutos, aceptando que no es tiempo real.

## Hardware del host

- CPU: AMD Ryzen 7 5700G (8 núcleos, 16 hilos).
- GPU: AMD Radeon RX 6600, 8 GB VRAM. ROCm con `HSA_OVERRIDE_GFX_VERSION=10.3.0` o fallback Vulkan.
- RAM: 32 GB.
- SO: Linux.

Considerar estas restricciones al proponer soluciones: nada de modelos que no quepan en offloading CPU+GPU razonable, nada que asuma CUDA o GPUs Nvidia. Para Stable Diffusion, asumir que SDXL en precisión completa no cabrá; usar cuantización o modelos derivados ligeros.

## Comandos frecuentes

- Ejecutar tests: `cd backend && pytest`
- Ejecutar tests con cobertura: `cd backend && pytest --cov=cimiento`
- Lint: `cd backend && ruff check .`
- Formato: `cd backend && ruff format .`
- Type-check: `cd backend && mypy src/`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
- Listar modelos Ollama: `ollama list`
- Levantar producto base: `cd infra/docker && docker compose up --build -d`
- Levantar servicios IA opcionales: `cd infra/docker && docker compose --profile ai up -d`
- Detener infraestructura: `cd infra/docker && docker compose down`

## Estado actual

Fase 4 completada. El producto base es usable en local sin copiloto de IA.

Próximo foco: Fase 5 — Copiloto conversacional con LangGraph y Ollama sobre la API y la UI ya operativas.

## Fases del proyecto

- [x] **Fase 1**: Solver aislado. Schemas Pydantic, solver CP-SAT para planta rectangular, visualización SVG.
- [x] **Fase 2**: Geometría y exportación BIM. Shapely para 2D, IfcOpenShell para IFC (canónico), ezdxf para DXF derivado, openpyxl para reportes.
- [x] **Fase 3**: Complejidad real. Multi-planta, núcleos de comunicación vertical, aparcamiento subterráneo, solares no rectangulares.
- [x] **Fase 4**: Web básica. FastAPI, visor IFC navegable, frontend React, upload/edición de solar, generación y descarga de outputs.
- [ ] **Fase 5**: Copiloto conversacional. LangGraph con agentes, tool-calling hacia el solver, ciclos de validación.
- [ ] **Fase 6**: RAG normativo. Indexación en Qdrant del CTE y ordenanzas, agente normativo consultando contra la base vectorial.
- [ ] **Fase 7**: Ingesta visual (Capa 0). Modelo de visión + OpenCV para convertir planos JPG/PNG en geometría base. Integración con el solver como input opcional.
- [ ] **Fase 8**: Visualización fotorrealista (Capa 6). Pipeline Blender headless + ComfyUI/SDXL + ControlNet. Generación de renders a partir del IFC con opción de imagen de referencia estética.

## Qué NO hacer en la fase actual

- No crear código de RAG ni indexación vectorial (pertenece a Fase 6).
- No implementar ingesta visual de planos (pertenece a Fase 7).
- No implementar pipeline de render fotorrealista (pertenece a Fase 8).
- No añadir dependencias al `pyproject.toml` sin consultar.
- No romper la regla de oro: el LLM orquesta, pero no calcula geometría ni optimización.

## Cómo colaborar con el usuario

- Una tarea verificable por prompt. Si una petición del usuario parece demasiado amplia, proponer dividirla antes de ejecutar.
- Preferir tests antes que código. Ante una funcionalidad nueva, proponer el test primero.
- Explicar decisiones técnicas cuando haya alternativas razonables. El usuario quiere entender, no solo recibir código.
- Cuando una decisión sea significativa (nueva dependencia, cambio de enfoque, excepción a un principio), proponer redactar un ADR en `docs/decisions/` numerado secuencialmente.
- Después de cambios importantes, recordar al usuario ejecutar tests y hacer commit.
- No modificar archivos fuera de la carpeta de la tarea actual salvo que sea necesario y esté justificado.
- Recordar que el proyecto se desarrolla por fases secuenciales. Si una petición del usuario entra en territorio de una fase futura, señalarlo y proponer posponerla salvo que el usuario explícitamente quiera adelantar trabajo.
