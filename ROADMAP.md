# Roadmap del Proyecto

Visión general de las fases del proyecto, objetivos por etapa
y estado actual de desarrollo.

---

## Estado actual
**Versión:** 1.0.0
**Fase:** Mantenimiento — todas las fases completadas
**Última actualización:** 2026-04-22

---

## Visión del producto
Cimiento es un copiloto local para anteproyecto residencial que permite pasar
de requisitos de programa y normativa a una propuesta espacial validada y exportable
en IFC, con trazabilidad técnica y control total de datos en entorno local.

---

## Fases del proyecto

### ✅ Fase 1 — Solver aislado [completada — 2026-04-20]
**Objetivo:** Resolver la distribución base en solares rectangulares.
- [x] Schemas Pydantic base para entrada/salida del solver
- [x] Modelo CP-SAT con restricciones de no solape
- [x] Visualización SVG de solución
- [x] Documentación de gobierno técnico base (CHANGELOG, DECISIONS y ROADMAP)

---

### ✅ Fase 2 — Geometría y exportación BIM [completada — 2026-04-20]
**Objetivo:** Convertir la solución abstracta en modelo constructivo exportable.
- [x] Schemas arquitectónicos (muros, espacios, forjados, aberturas)
- [x] Builder geométrico desde Solution
- [x] Exportador IFC4
- [x] Exportadores DXF y XLSX derivados

---

### ✅ Fase 3 — Geometría avanzada [completada — 2026-04-20]
**Objetivo:** Soportar casos reales no rectangulares y mejorar fidelidad BIM.
- [x] Soporte completo de solares poligonales en solver y geometry (ADR 0006)
- [x] Estrategia de muros y aberturas (ADR 0005)
- [x] Solver con núcleos de comunicación vertical (escaleras y ascensores)
- [x] Auditoría de seguridad inicial documentada

---

### ✅ Fase 4 — API y visualización web [completada — 2026-04-20]
**Objetivo:** Exponer el sistema en una interfaz usable de extremo a extremo.
- [x] Endpoints FastAPI para flujo principal
- [x] Frontend React + TypeScript en alemán para listado, edición y detalle de proyecto
- [x] Flujo completo sin LLM: proyecto, generación, outputs y visor IFC
- [x] Progreso de generación en vivo mediante WebSocket
- [x] Descarga de IFC, DXF, XLSX y SVG desde la UI
- [x] Docker Compose con frontend y backend como servicios del producto

---

### ✅ Fase 5 — Copiloto conversacional [completada — 2026-04-21]
**Objetivo:** Añadir interacción asistida para iterar propuestas rápidamente.
- [x] Cliente Ollama async base con `chat(...)` y wrapper HTTP desacoplado de FastAPI
- [x] Selección de modelo por rol desde configuración centralizada (ADR 0008)
- [x] Grafo de agentes con LangGraph y nodos por responsabilidad (ADR 0009)
- [x] Integración Ollama en agentes según tipo de tarea
- [x] Validación de entrada/salida de herramientas con Pydantic
- [x] Flujo conversacional sobre proyectos, versiones y generación integrado en la UI

---

### ✅ Fase 6 — RAG normativo [completada — 2026-04-21]
**Objetivo:** Integrar consulta normativa contextual para validar propuestas.
- [x] Indexación de normativa alemana en Qdrant con `nomic-embed-text` (ADR 0011)
- [x] Recuperación contextual por artículo con citas trazables
- [x] Agente normativo que solo recupera y cita, sin razonamiento propio (ADR 0010)

---

### ✅ Fase 7 — Ingesta visual de planos [completada — 2026-04-21]
**Objetivo:** Convertir imagen de plano/croquis en geometría base para el solver.
- [x] Pipeline OpenCV para extracción de contornos y referencias geométricas (ADR 0012)
- [x] `qwen2.5vl:7b` para interpretación semántica de planos (ADR 0013)
- [x] Revisión humana obligatoria antes de consolidar al solver

---

### ✅ Fase 8 — Render fotorrealista y difusión [completada — 2026-04-22]
**Objetivo:** Generar renders de presentación y variantes generativas desde el IFC.
- [x] Blender headless para render determinista IFC → PNG (ADR 0014)
- [x] SD 1.5 + ControlNet (depth + canny) + InstructPix2Pix via diffusers (ADR 0016)
- [x] Galería de renders y difusión con progreso, referencia visual opcional y descarga HQ
- [x] Render e imagen generativa nunca modifican el IFC canónico

---

## Trabajo abierto para v1.x

Estas mejoras no invalidan v1.0 y no requieren cambiar la arquitectura base:

| Área | Descripción |
|------|-------------|
| BIM | Evaluar IFC4.3 cuando el ecosistema de herramientas lo permita |
| Agentes | Persistencia durable del chat más allá de `MemorySaver` |
| RAG | Ampliar corpus normativo por *Land* y tipología de edificio |
| Render | Optimizar estrategia multi-hardware (AMD, Nvidia, cloud opt-in) |
| Difusión | Migrar a SDXL cuando InstructPix2Pix para SDXL sea estable en diffusers |
| Difusión | Coordinar `_LOADED_PIPELINES` entre workers si se escala a producción multi-proceso |

---

## Descartado / No hacer

| Idea | Razón para no hacerlo |
|------|----------------------|
| Sustituir OR-Tools CP-SAT por otro solver | Rompe decisiones aceptadas y no aporta valor frente al alcance vigente |
| Tratar DXF/XLSX como fuente de verdad del modelo | Se pierde semántica BIM; el canon del proyecto es IFC |
| Delegar geometría al LLM | Principio fundacional no negociable de la arquitectura |

---

## Métricas de éxito del proyecto

- [x] Pipeline funcional de extremo a extremo: requisitos → IFC → render
- [x] Copiloto conversacional en alemán operativo
- [x] RAG normativo local con citas trazables
- [x] Ingesta visual bajo revisión humana
- [ ] Tiempo total de pipeline dentro de límites operativos definidos por caso
- [ ] Cobertura de tests alineada con los umbrales definidos (80 % / 70 % por módulo)
