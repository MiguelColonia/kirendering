# Roadmap del Proyecto

Vision general de las fases del proyecto, objetivos por etapa
y estado actual de desarrollo.

---

## Estado actual
**Version:** 0.1.0
**Fase:** Fase 3 — Geometria avanzada y solver con dimensiones variables
**Ultima actualizacion:** 2026-04-20

---

## Vision del producto
Cimiento sera un copiloto local para anteproyecto residencial que permita pasar
de requisitos de programa y normativa a una propuesta espacial validada y exportable
en IFC, con trazabilidad tecnica y control total de datos en entorno local.

---

## Fases del proyecto

### ✅ Fase 1 — Solver aislado [completada]
**Objetivo:** Resolver la distribucion base en solares rectangulares.
**Criterio de exito:** Obtener soluciones FEASIBLE/OPTIMAL reproducibles con tests.
**Fecha real:** 2026-04-20
- [x] Schemas Pydantic base para entrada/salida del solver
- [x] Modelo CP-SAT con restricciones de no solape
- [x] Visualizacion SVG de solucion

---

### ✅ Fase 2 — Geometria y exportacion BIM [completada]
**Objetivo:** Convertir la solucion abstracta en modelo constructivo exportable.
**Criterio de exito:** Pipeline solver -> building -> IFC/DXF/XLSX verificable por tests.
**Fecha real:** 2026-04-20
- [x] Schemas arquitectonicos (muros, espacios, forjados, aberturas)
- [x] Builder geometrico desde Solution
- [x] Exportador IFC4
- [x] Exportadores DXF y XLSX derivados

---

### 🔄 Fase 3 — Geometria avanzada [en progreso]
**Objetivo:** Soportar casos reales no rectangulares y mejorar fidelidad BIM.
**Criterio de exito:** Resolver y exportar correctamente solares irregulares y elementos complejos.
**Fecha estimada:** 2026-06-30
- [ ] Soporte completo de solares poligonales en solver y geometry
- [ ] Muros diagonales y cortes reales para aberturas
- [ ] Solver con dimensiones variables de unidad
- [ ] Nucleos de comunicacion vertical (escaleras y ascensores)

---

### 📅 Fase 4 — API y visualizacion web [planificada]
**Objetivo:** Exponer el sistema en una interfaz usable de extremo a extremo.
**Criterio de exito:** Usuario puede subir parametros y descargar outputs desde UI web.
**Fecha estimada:** 2026-08-31
- [ ] Endpoints FastAPI para flujo principal
- [ ] Frontend React minimo con visor IFC.js
- [ ] Carga de solar y descarga de resultados

---

### 💡 Fase 5 — Copiloto conversacional [idea]
**Objetivo:** Añadir interaccion asistida para iterar propuestas rapidamente.
**Criterio de exito:** Flujo conversacional estable con tool-calling validado por schemas.
**Fecha estimada:** por definir
- [ ] Grafo de agentes con LangGraph
- [ ] Integracion Ollama segun tipo de tarea
- [ ] Validacion de entrada/salida de herramientas con Pydantic

---

### 🔬 Fase 6 — RAG normativo [idea]
**Objetivo:** Integrar consulta normativa contextual para validar propuestas.
**Criterio de exito:** Recomendaciones y alertas normativas trazables a fuente.
**Fecha estimada:** por definir
- [ ] Indexacion de CTE y ordenanzas locales en Qdrant
- [ ] Recuperacion contextual para agente normativo
- [ ] Evidencias citables por articulo/apartado

---

### 🔬 Fase 7 — Ingesta visual de planos [idea]
**Objetivo:** Convertir imagen de plano/croquis en geometria base para el solver.
**Criterio de exito:** Input visual usable como restriccion inicial revisable por usuario.
**Fecha estimada:** por definir
- [ ] Pipeline vision + OpenCV para extraer contornos y referencias
- [ ] Normalizacion a schema de geometria base
- [ ] Validacion manual previa a consolidacion

---

### 🔬 Fase 8 — Render fotorrealista [idea]
**Objetivo:** Generar renders de presentacion desde IFC sin perder trazabilidad.
**Criterio de exito:** Render de calidad en 1-2 minutos sobre hardware objetivo.
**Fecha estimada:** por definir
- [ ] Blender headless para pases geometrico-tecnicos
- [ ] ComfyUI/SDXL + ControlNet condicionado por BIM
- [ ] Opcion de referencia estetica por imagen

---

## Descartado / No hacer
Cosas que se han evaluado y conscientemente decidido no hacer.
Documentar el porque evita discutirlo repetidamente.

| Idea | Razon para no hacerlo |
|---|---|
| Sustituir OR-Tools CP-SAT por otro solver en fase actual | Rompe decisiones aceptadas y no aporta valor inmediato frente al alcance vigente |
| Tratar DXF/XLSX como fuente de verdad del modelo | Se pierde semantica BIM; el canon del proyecto es IFC |

---

## Metricas de exito del proyecto
Como sabremos que el proyecto ha tenido exito:
- [ ] Tiempo total de pipeline por caso objetivo dentro de limites operativos definidos
- [ ] Tasa de casos validos (sin errores de exportacion) por encima del objetivo acordado
- [ ] Cobertura de tests alineada con el umbral definido por el equipo
