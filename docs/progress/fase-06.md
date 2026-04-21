# Fase 6 — RAG normativo sobre Qdrant

**Estado:** Completada  
**Fecha:** 2026-04-21

---

## Qué se logró

### RAG normativo local integrado en el backend

La capa RAG ya forma parte del backend y opera íntegramente en local con Ollama + Qdrant:

- `cimiento.rag.ingestion` extrae, limpia y fragmenta normativa alemana.
- `cimiento.rag.retriever` genera embeddings con `nomic-embed-text` y consulta Qdrant.
- `cimiento.llm.tools.query_regulation` dejó de ser un stub puro y ahora usa búsqueda vectorial real cuando Qdrant está disponible.
- `cimiento.api.main` inicializa `AsyncQdrantClient` en el ciclo de vida de FastAPI y lo inyecta en el grafo conversacional.

La configuración queda centralizada en `Settings`:

```python
qdrant_host = "localhost"
qdrant_port = 6333
qdrant_collection = "normativa"
ollama_model_embed = "nomic-embed-text"
```

### Chunking jurídico por artículo, no por ventana fija

La decisión clave de la fase es que la unidad primaria de indexación sea el **artículo normativo completo** (`§ N`, `§ Na`, `Anlage N`) y no ventanas arbitrarias de tokens.

Flujo de chunking:

1. Detectar secciones estructurales (`Abschnitt`, `Teil`, `Kapitel`, `Anhang`, `Anlage`).
2. Detectar artículos `§ N` al comienzo de línea.
3. Generar un `RegulationChunk` por artículo con ID determinista.
4. Si el artículo supera el umbral práctico (~1 200 palabras), subdividir por `Absatz (1), (2), (3)`.

Esto preserva la unidad semántica natural del texto jurídico alemán, reduce duplicación de embeddings y mantiene juntas excepciones, referencias cruzadas y condiciones que quedarían rotas con ventanas fijas.

### Ingesta mixta PDF + XML GII

La tubería de ingesta soporta ahora dos formatos de origen:

| Formato | Estrategia |
|---|---|
| PDF oficial | `pdfplumber` + limpieza de cabeceras/paginación + chunking por artículo |
| XML GII (`Gesetze im Internet`) | parsing estructurado de `<norm>` y extracción directa de `enbez`, `titel` y `<Content>` |

Cuando existe XML GII, se prioriza porque evita artefactos de OCR o maquetación PDF. En esta fase, el corpus de referencia versionado en el repo queda compuesto por:

- `data/normativa/de/GEG.xml`
- `data/normativa/de/MBO.pdf`

La ingesta operativa se ejecuta con:

```bash
cd backend
python scripts/ingest_regulations.py --dry-run
python scripts/ingest_regulations.py --recreate
```

### Recuperación trazable y respuesta con citas

El grafo conversacional incorpora un nuevo nodo `answer_with_regulation` y una ruta específica desde `START`:

```text
START
 ├─ consulta normativa directa → answer_with_regulation → END
 └─ petición de diseño        → extract_requirements → validate_normative → ...
```

La clasificación inicial distingue entre:

- **consulta normativa**: presencia de `§`, `GEG`, `MBO`, `BauNVO`, `WoFlV`, `LBO`, `DIN 18040`
- **petición de diseño**: mensajes con dimensiones de solar como `20x30` o `15×20`

El nodo normativo:

1. Recupera los chunks más relevantes desde Qdrant.
2. Los formatea como contexto citables en el patrón `[DOC §N]`.
3. Instruye al LLM para responder **solo** con ese contexto y abstenerse si falta base documental.

Ejemplo de contexto entregado al LLM:

```text
[GEG § 10] Anforderungen an zu errichtende Wohngebäude
Der Jahres-Primärenergiebedarf ...

[MBO § 37] Aufzüge
Aufzüge sind in Gebäuden mit mehr als vier Vollgeschossen erforderlich ...
```

### Fallback útil en desarrollo

Si Qdrant no está disponible o falla la búsqueda vectorial, el sistema recae en un fallback mock de normativa alemana formateado con el mismo estilo de citas. Esto mantiene utilizable el flujo de chat local y permite tests del grafo sin infraestructura externa.

### Cobertura de tests de Fase 6

Se añadió una batería específica para la nueva capa:

- `tests/unit/test_rag/test_chunking.py` — chunking por artículo, preámbulo, limpieza PDF e IDs deterministas.
- `tests/unit/test_rag/test_retriever.py` — adaptación de resultados Qdrant, filtros y formato de contexto.
- `tests/unit/test_rag/test_fidelity.py` — fidelidad extremo a extremo del nodo `answer_with_regulation`, reglas de cita y clasificación normativa vs. diseño.

---

## Decisiones técnicas consolidadas

- **Qdrant** es la base vectorial local para normativa.
- **`nomic-embed-text`** es el modelo de embedding canónico.
- **`RegulationChunk`** es la unidad de intercambio entre ingesta, retriever y LLM.
- **El artículo (§) es la unidad primaria de chunking.** Solo se subdivide por `Absatz` si el tamaño lo exige.
- **El agente normativo no razona sobre normativa fuera del contexto recuperado.** Ver ADR 0010.
- **Cuando existe XML GII, se prefiere a PDF** por calidad estructural. Ver ADR 0011.

---

## Limitaciones conocidas al cerrar Fase 6

- El chat multi-turno del grafo sigue usando `MemorySaver`; la memoria no sobrevive reinicios del backend.
- El corpus versionado en el repositorio es mínimo; el pipeline soporta LBO por documento, pero su incorporación sigue siendo un trabajo de curación e indexación.
- La reindexación sigue siendo un proceso manual operado mediante script.
- Si Qdrant no está disponible, la experiencia sigue siendo útil pero pierde trazabilidad sobre corpus real y pasa a datos mock.

---

## Qué habilita Fase 7

- Añadir una capa de ingesta visual sin tocar el contrato entre RAG, solver y BIM.
- Extender el corpus normativo por Land o tipología manteniendo el mismo esquema `RegulationChunk`.
- Evaluar persistencia del checkpointer sin alterar la arquitectura del RAG ya consolidada.
