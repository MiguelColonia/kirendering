# Roadmap del Proyecto

Visión general de las fases del proyecto, objetivos por etapa
y estado actual de desarrollo.

---

## Estado actual
**Versión:** 0.1.0
**Fase:** Fase 5 — infraestructura conversacional base en progreso
**Última actualización:** 2026-04-20

---

## Visión del producto
Cimiento será un copiloto local para anteproyecto residencial que permita pasar
de requisitos de programa y normativa a una propuesta espacial validada y exportable
en IFC, con trazabilidad técnica y control total de datos en entorno local.

---

## Fases del proyecto

### ✅ Fase 1 — Solver aislado [completada]
**Objetivo:** Resolver la distribución base en solares rectangulares.
**Criterio de éxito:** Obtener soluciones FEASIBLE/OPTIMAL reproducibles con tests.
**Fecha real:** 2026-04-20
- [x] Schemas Pydantic base para entrada/salida del solver
- [x] Modelo CP-SAT con restricciones de no solape
- [x] Visualización SVG de solución
- [x] Documentación de gobierno técnico base (CHANGELOG, DECISIONS y ROADMAP)

---

### ✅ Fase 2 — Geometria y exportacion BIM [completada]
**Objetivo:** Convertir la solución abstracta en modelo constructivo exportable.
**Criterio de éxito:** Pipeline solver -> building -> IFC/DXF/XLSX verificable por tests.
**Fecha real:** 2026-04-20
- [x] Schemas arquitectónicos (muros, espacios, forjados, aberturas)
- [x] Builder geométrico desde Solution
- [x] Exportador IFC4
- [x] Exportadores DXF y XLSX derivados

---

### 🔄 Fase 3 — Geometria avanzada [en progreso]
**Objetivo:** Soportar casos reales no rectangulares y mejorar fidelidad BIM.
**Criterio de éxito:** Resolver y exportar correctamente solares irregulares y elementos complejos.
**Fecha estimada:** 2026-06-30
- [ ] Soporte completo de solares poligonales en solver y geometry
- [ ] Muros diagonales y cortes reales para aberturas
- [ ] Solver con dimensiones variables de unidad
- [x] Núcleos de comunicación vertical (escaleras y ascensores)
- [x] Auditoría de seguridad inicial documentada

---

### ✅ Fase 4 — API y visualizacion web [completada]
**Objetivo:** Exponer el sistema en una interfaz usable de extremo a extremo.
**Criterio de éxito:** Usuario puede subir parámetros y descargar outputs desde UI web.
**Fecha real:** 2026-04-20
- [x] Endpoints FastAPI para flujo principal
- [x] Frontend React + TypeScript en alemán para listado, edición y detalle de proyecto
- [x] Flujo completo sin LLM: proyecto, generación, outputs y visor IFC
- [x] Progreso de generación en vivo mediante WebSocket
- [x] Descarga de IFC, DXF, XLSX y SVG desde la UI
- [x] Docker Compose con frontend y backend como servicios del producto
- [x] Test unitario base del endpoint `/health`

---

### 🔄 Fase 5 — Copiloto conversacional [en progreso]
**Objetivo:** Añadir interacción asistida para iterar propuestas rápidamente.
**Criterio de éxito:** Flujo conversacional estable con tool-calling validado por schemas.
**Fecha estimada:** por definir
- [x] Cliente Ollama async base con `chat(...)` y wrapper HTTP desacoplado de FastAPI
- [x] Selección de modelo por rol (`planner`, `validator`, `normative`, `chat`, `coder`) desde configuración centralizada
- [x] Soporte inicial de `response_format=json_schema` con tests y smoke test real local
- [ ] Grafo de agentes con LangGraph
- [ ] Integración Ollama en agentes y grafos según tipo de tarea
- [ ] Validación de entrada/salida de herramientas con Pydantic
- [ ] Primer flujo conversacional sobre proyectos, versiones y generación

---

### 🔬 Fase 6 — RAG normativo [idea]
**Objetivo:** Integrar consulta normativa contextual para validar propuestas.
**Criterio de éxito:** Recomendaciones y alertas normativas trazables a fuente.
**Fecha estimada:** por definir
- [ ] Indexación de CTE y ordenanzas locales en Qdrant
- [ ] Recuperacion contextual para agente normativo
- [ ] Evidencias citables por artículo/apartado

---

### 🔬 Fase 7 — Ingesta visual de planos [idea]
**Objetivo:** Convertir imagen de plano/croquis en geometria base para el solver.
**Criterio de éxito:** Input visual usable como restricción inicial revisable por usuario.
**Fecha estimada:** por definir
- [ ] Pipeline vision + OpenCV para extraer contornos y referencias
- [ ] Normalización a schema de geometría base
- [ ] Validación manual previa a consolidación

---

### 🔬 Fase 8 — Render fotorrealista [idea]
**Objetivo:** Generar renders de presentacion desde IFC sin perder trazabilidad.
**Criterio de éxito:** Render de calidad en 1-2 minutos sobre hardware objetivo.
**Fecha estimada:** por definir
- [ ] Blender headless para pases geométrico-técnicos
- [ ] ComfyUI/SDXL + ControlNet condicionado por BIM
- [ ] Opción de referencia estética por imagen

---

## Descartado / No hacer
Cosas que se han evaluado y conscientemente decidido no hacer.
Documentar el porqué evita discutirlo repetidamente.

| Idea | Razón para no hacerlo |
|---|---|
| Sustituir OR-Tools CP-SAT por otro solver en fase actual | Rompe decisiones aceptadas y no aporta valor inmediato frente al alcance vigente |
| Tratar DXF/XLSX como fuente de verdad del modelo | Se pierde semántica BIM; el canon del proyecto es IFC |

---

## Metricas de exito del proyecto
Cómo sabremos que el proyecto ha tenido éxito:
- [ ] Tiempo total de pipeline por caso objetivo dentro de limites operativos definidos
- [ ] Tasa de casos válidos (sin errores de exportación) por encima del objetivo acordado
- [ ] Cobertura de tests alineada con el umbral definido por el equipo
