# ADR 0011 — Arquitectura RAG local y chunking por artículo para normativa alemana

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Cierre de Fase 6 — RAG normativo local sobre Qdrant

---

## Contexto

Fase 6 introduce una capa RAG para responder y validar normativa de edificación alemana sin depender del conocimiento paramétrico del LLM. La arquitectura debía resolver simultáneamente cuatro restricciones:

1. Ejecutar todo en local, sin servicios cloud.
2. Mantener trazabilidad jurídica por artículo.
3. Soportar fuentes heterogéneas (PDF oficiales y XML GII).
4. Minimizar el riesgo de fragmentar mal el texto normativo al indexarlo.

La decisión principal no era solo qué base vectorial usar, sino también **cuál era la unidad semántica correcta de chunking** para derecho positivo alemán.

---

## Decisión

Se adopta la siguiente arquitectura:

1. **Qdrant** como base vectorial local.
2. **Ollama + `nomic-embed-text`** como servicio de embeddings.
3. **`RegulationChunk`** como unidad canónica de almacenamiento y recuperación.
4. **Chunking primario por artículo** (`§ N`, `§ Na`, `Anlage N`), con subdivisión excepcional por `Absatz` solo cuando un artículo sea demasiado largo.
5. **Preferencia por XML GII** frente a PDF cuando ambas fuentes existan para la misma norma.

---

## Decisión 1 — Qdrant como base vectorial local

### Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Qdrant | API simple, buen soporte async, filtros por payload, operación local ligera | Nueva dependencia operativa |
| PostgreSQL + pgvector | Reutiliza la BD del producto | Mezcla persistencia transaccional y búsqueda semántica; tuning peor para este caso |
| FAISS embebido | Muy rápido y sin servicio externo | Sin payload store robusto ni filtros tan cómodos para documentos/secciones |

### Por qué se elige Qdrant

- Encaja bien con la operación local del producto.
- Permite filtrar por `document`, `section` y metadatos sin diseñar una capa adicional.
- Mantiene desacopladas la persistencia transaccional del producto y la búsqueda semántica normativa.

---

## Decisión 2 — Unidad de chunking: artículo jurídico, no ventana fija

### Alternativas descartadas

| Alternativa | Por qué se descartó |
|---|---|
| Ventanas fijas de tokens con solape | Rompen un mismo `§` entre fragmentos y separan excepciones, remisiones y condiciones |
| Chunking por párrafo o sentencia | Demasiado fino para texto jurídico; pierde la unidad obligacional completa |
| Documento completo | Reduce precisión de recuperación y diluye la señal semántica del embedding |

### Por qué el artículo es la unidad correcta

En normativa alemana, el `§` es la unidad jurídica natural. Un artículo suele contener:

- la regla principal,
- sus excepciones,
- referencias a `Absatz`, `Satz` o `Anlage`,
- y el título jurídico útil para citación.

Partir esa unidad con ventanas arbitrarias hace que la recuperación sea menos fiable y que el LLM reciba contexto incompleto aunque el embedding haya acertado parcialmente.

### Regla de fallback

Si un artículo supera el umbral práctico de tamaño, **se subdivide por `Absatz`**. El `Absatz` es la segunda unidad semántica natural del derecho alemán y conserva mejor la estructura jurídica que cualquier corte por tokens.

---

## Decisión 3 — Preferir XML GII a PDF cuando exista

### Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| PDF como fuente única | Universal y fácil de obtener | Ruido de maquetación, cabeceras, paginación, OCR y cortes visuales |
| XML GII cuando exista, PDF como fallback | Estructura explícita por norma/artículo, menos limpieza, mejor fidelidad | No todas las normas relevantes están disponibles igual de bien en GII |

### Decisión tomada

Cuando la norma esté disponible en formato XML de **Gesetze im Internet**, ese formato es preferente. El PDF se mantiene como fallback para documentos sin XML usable o para fuentes fuera de GII.

Razones:

- El XML ya expone `enbez`, `titel` y bloques de contenido.
- Evita errores de extracción causados por columnas, pies de página y cabeceras.
- Reduce el trabajo heurístico de limpieza antes del embedding.

---

## Consecuencias

**Positivas:**

- Recuperación más trazable y estable.
- Menor número de chunks y menor coste de embedding que con ventanas fijas.
- Mejor alineación entre recuperación, cita `[DOC §N]` y lectura humana del arquitecto.
- Pipeline robusto ante mezcla de fuentes PDF y XML.

**Negativas:**

- La calidad depende de detectar correctamente los marcadores `§`, `Abschnitt` y `Absatz`.
- Algunas normas pueden no disponer de XML y seguirán sujetas a artefactos PDF.
- La reindexación completa debe repetirse cuando cambien el corpus o las reglas de chunking.

---

## Revisión

Revisar esta ADR si ocurre alguno de estos supuestos:

- Se incorpora normativa masiva cuyo tamaño haga inviable el chunking por artículo.
- Se detecta que artículos muy largos degradan la precisión incluso con subdivisión por `Absatz`.
- Se decide unificar recuperación semántica y persistencia transaccional en una misma base.
- Se introduce un reranker adicional y cambia la unidad óptima de recuperación.
