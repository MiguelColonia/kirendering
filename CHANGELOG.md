# Changelog

Registro de todos los cambios relevantes del proyecto ordenados
por versión. Sigue el estándar Keep a Changelog y Semantic Versioning.

## Versionado
- MAJOR (1.0.0): cambios incompatibles con versiones anteriores
- MINOR (0.1.0): nueva funcionalidad compatible con lo anterior
- PATCH (0.0.1): corrección de bugs compatible con lo anterior

---

## [Unreleased]

### ➕ Añadido
- **`render/blender_compat.py`**: módulo de compatibilidad entre versiones de Blender; centraliza la elección de `sky_type` (Nishita → PREETHAM → fallback) para que el pipeline funcione con Blender 3.x, 4.x y 5.x sin condicionales dispersos.
- **`scripts/check_blender_gpu.py`**: herramienta de diagnóstico GPU/HIP para Blender Cycles en el host. Detecta backends disponibles, dispositivos HIP, versión ROCm y guía la acción correctiva según el entorno (Blender 5.1 + ROCm 6+ requerido para HIP).
- **`tests/unit/test_blender_compat.py`**: cobertura unitaria de `blender_compat.choose_sky_type` con todos los casos de degradación de sky type.
- **`tests/unit/test_check_blender_gpu.py`**: tests del script de diagnóstico GPU (mocking de subprocess y Blender probe).
- **`tests/unit/test_diffusion_pipeline.py`**: tests unitarios del pipeline de difusión generativa.
- **`tests/unit/test_render_manual_script.py`**: tests del script de render manual que validan configuración y argumentos CLI.
- **`frontend/src/features/chat/ChatPanel.test.tsx`**: tests de componente para el panel de chat en alemán.
- **`docs/manual-usuario.md`**: manual de usuario del producto en español.
- **`docs/qa/requirements-test.md`**: matriz de requisitos y casos de test de aceptación.
- **`docs/qa/risk-based-testing.md`**: estrategia de testing basada en riesgos para el mantenimiento v1.x.

### 🐛 Corregido
- **`vision/preprocessing.py`**: `extract_scale` usaba `role="chat"` (modelo de texto) en lugar de `role="vision"`, haciendo que el VLM ignorase la imagen adjunta. Corregido a `role="vision"` con prompt en inglés y `format="json"`.
- **`api/main.py`**: timeout del `OllamaClient` aumentado a 300 s para evitar `ReadTimeout` en la primera carga del modelo `qwen2.5vl:7b` (6 GB, ~120 s de carga en frío).
- **`api/routers/chat.py`**: eliminado endpoint `POST /api/projects/{id}/chat` huérfano; el frontend solo usa WebSocket. Se eliminan también las importaciones y schemas no utilizados.
- **`api/schemas.py`**: tipos de los campos `view` y `mode` en las respuestas de galería afinados a `Literal` y `DiffusionMode` para mayor seguridad de tipos.
- **`bim/ifc_exporter.py`**, **`render/blender_pipeline.py`**, **`vision/interpreter.py`**: todos los mensajes de advertencia orientados al usuario traducidos de español a alemán.
- **`test_hardware_benchmark.py`**: los tests de benchmark fallaban de forma intermitente cuando el modelo de 14B quedaba cargado en VRAM antes del test del coder-7B. Añadido `setup_method` con `_ollama_unload_all()` y calentamiento previo en `_benchmark_model` para aislar cada benchmark y medir solo la velocidad de generación con el modelo ya en VRAM.
- **`test_vision_preprocessing.py`**, **`test_vision_interpreter.py`**: ajustados para reflejar el cambio de `role` y los mensajes de advertencia en alemán.

### 🔄 Cambiado
- **`pyproject.toml`**: dependencias de PyTorch alineadas con ROCm 5.7 (`torch==2.3.1`, `torchvision==0.18.1`, `torchaudio==2.3.1`) mediante `[tool.uv.sources]` para garantizar compatibilidad con la GPU AMD RX 6600. `transformers` acotado a `<5.0.0` por incompatibilidad de transformers 5.x con torch 2.3.x.
- **`.env`**: base de datos cambiada de SQLite a PostgreSQL (`postgresql+asyncpg://cimiento:cimiento@localhost:5432/cimiento`).
- **`.gitignore`**: añadido `data/qdrant_storage/` para excluir el almacenamiento en tiempo de ejecución de Qdrant.
- **`infra/docker/docker-compose.yml`**: ajuste menor de configuración del servicio.

---

## [1.0.0] — 2026-04-22

### ➕ Añadido
- Pipeline de difusión generativa (`diffusion/`) con SD 1.5, ControlNet (depth + canny) e InstructPix2Pix via diffusers HuggingFace. ADR 0016.
- Lazy loading de pipelines de difusión: el servidor arranca aunque `diffusers`/`torch` no estén instalados.
- Endpoints de difusión: `POST /api/projects/{id}/diffusion`, galería `GET /api/projects/{id}/diffusion`, progreso vía WebSocket.
- UI de galería de difusión en frontend con imagen de referencia opcional, prompt en alemán y descarga HQ.
- ADR 0016 para fijar modelo base SD 1.5, adaptadores ControlNet e InstructPix2Pix, y estrategia multi-hardware.
- Pipeline de render headless Blender Cycles a partir del IFC canónico (`render/blender_pipeline.py`). ADR 0014.
- UI de galería de renders por proyecto (`/projekte/:id/renders`) con progreso, vista exterior/interior y descarga HQ.
- Pipeline de visión (`vision/`) con OpenCV para extracción geométrica y `qwen2.5vl:7b` para interpretación semántica, bajo revisión humana obligatoria. ADR 0012, ADR 0013.
- RAG normativo local (`rag/`) con Qdrant, embeddings `nomic-embed-text` y chunking por artículo jurídico. ADR 0011.
- Agente normativo que solo recupera y cita, sin razonamiento propio. ADR 0010.
- Grafo de agentes LangGraph con nodos y asignación de modelos por rol (planner, validator, normative, chat, coder). ADR 0009.
- Cliente async de Ollama en `backend/src/cimiento/llm/client.py` con `model_for_role`, soporte de `tools` y `response_format=json_schema`. ADR 0008.
- Soporte de solares poligonales en solver y geometry. ADR 0006.
- Estrategia de muros y aberturas en el modelo BIM. ADR 0005.
- Visor IFC web con navegación espacial, árbol de estructura, propiedades y recortes por Geschoss.
- Copiloto conversacional en alemán integrado en la UI con WebSocket.
- Exportaciones derivadas en DXF, XLSX y SVG desde el IFC canónico.
- Docker Compose de producción (`infra/docker/docker-compose.prod.yml`).
- ADR 0015 de cierre v1.0 como índice comentado de todas las decisiones acumuladas.
- Tests unitarios y de integración para todos los módulos principales.
- Script manual `backend/scripts/test_render_manual.py` para validar el pipeline de render sin UI.
- Guías de instalación multilingües y multi-hardware en `docs/installation/README.md`.

### 🔄 Cambiado
- `CLAUDE.md` actualizado al estado de mantenimiento v1.0 con todas las fases completadas.
- `README.md` bilingüe (español + alemán) con descripción completa del producto.
- `DECISIONS.md` con los ADRs 0001 a 0016 registrados.

### 🔒 Seguridad
- Auditoría de seguridad inicial documentada con foco en configuración, CORS, inyección y hardening HTTP.

---

## [0.1.0] — 2026-04-20
### ➕ Añadido
- Estructura inicial del proyecto.
- Solver CP-SAT base para distribución residencial.
- Schemas Pydantic v2 para geometría, programa y solución.
- Exportación BIM inicial a IFC4, DXF y XLSX.
- Tests unitarios del endpoint `/health` en `backend/tests/unit/test_api_main.py`.
- Documentación de gobierno técnico base: `CHANGELOG.md`, `DECISIONS.md` y `ROADMAP.md`.
- ADR-0001 a ADR-0004: OR-Tools, Qwen sobre Llama, formulación CP-SAT, IFC4 canónico.
- ADR-0007 para fijar el stack frontend (React + TypeScript + Vite).
- ADR-0008 para fijar la abstracción base del cliente Ollama y el mapeo de modelos por rol.
- Dockerfiles de backend y frontend, más despliegue web completo en `infra/docker/docker-compose.yml`.
- Frontend React + TypeScript en alemán: listado, editor y detalle de proyecto, visor IFC, progreso de generación en vivo.
