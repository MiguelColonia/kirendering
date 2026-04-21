# Architecture Decision Records

Registro de decisiones arquitectónicas y técnicas relevantes tomadas
durante el proyecto. Documenta el contexto, la decisión y sus consecuencias.

---

## Plantilla ADR
### ADR-[número] — [Título de la decisión]
**Fecha:** YYYY-MM-DD
**Estado:** propuesta / aceptada / deprecada / reemplazada por ADR-XXX
**Decidido por:** [persona o equipo]

#### Contexto
Situación que motivó tomar esta decisión.
Qué problema había, qué restricciones existían.

#### Opciones consideradas
1. **Opción A** — descripción breve
   - ✅ Ventajas
   - ❌ Desventajas

2. **Opción B** — descripción breve
   - ✅ Ventajas
   - ❌ Desventajas

#### Decisión tomada
Qué se eligió y por qué. Razonamiento concreto.

#### Consecuencias
- ✅ Qué se gana con esta decisión
- ❌ Qué se sacrifica o qué deuda se asume
- ⚠️ Qué habrá que vigilar en el futuro

#### Revisión
Cuándo y bajo qué condiciones debería revisarse esta decisión.

---

## Registro de decisiones
<!-- Las más recientes primero -->

### ADR-0015 — Cierre v1.0: estado de decisiones acumuladas
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0015-cierre-v1-0-estado-de-decisiones-acumuladas.md

### ADR-0014 — Estrategia SD: diffusers vs ComfyUI, modelo y backend de inferencia
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0014-diffusers-vs-comfyui-sd-pipeline.md

### ADR-0013 — Modelo VLM local: qwen2.5vl:7b para interpretación de planos
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0013-vlm-local-qwen25vl-para-vision.md

### ADR-0012 — División OpenCV + VLM para ingesta visual de planos
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0012-division-opencv-vlm-para-ingesta-visual.md

### ADR-0011 — Arquitectura RAG local y chunking por artículo para normativa alemana
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0011-arquitectura-rag-y-chunking-normativo.md

### ADR-0010 — El agente normativo no razona: solo recupera y cita
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0010-agente-normativo-sin-razonamiento.md

### ADR-0009 — Arquitectura de agentes: LangGraph, nodos y asignación de modelos por rol
**Fecha:** 2026-04-21
**Estado:** aceptada
**Documento:** docs/decisions/0009-arquitectura-de-agentes-langgraph.md

### ADR-0008 — Cliente Ollama y modelos por rol
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0008-cliente-ollama-y-modelos-por-rol.md

### ADR-0007 — Stack frontend para Fase 4
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0007-stack-frontend-fase-4.md

### ADR-0006 — Solares poligonales
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0006-solares-poligonales.md

### ADR-0005 — Estrategia de muros y aberturas
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0005-estrategia-de-muros-y-aberturas.md

### ADR-0004 — IFC4 como formato canónico
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0004-ifc4-como-formato-canonico.md

### ADR-0003 — Formulación CP-SAT inicial
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0003-formulacion-cp-sat-inicial.md

### ADR-0002 — Qwen sobre Llama
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0002-qwen-sobre-llama.md

### ADR-0001 — Por qué OR-Tools
**Fecha:** 2026-04-20
**Estado:** aceptada
**Documento:** docs/decisions/0001-por-que-or-tools.md
