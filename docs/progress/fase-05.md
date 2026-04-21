# Fase 5 — Copiloto conversacional

**Estado:** Completada  
**Fecha:** 2026-04-21

---

## Qué se logró

### Grafo de agentes con LangGraph

El copiloto opera mediante un `StateGraph` de cinco nodos que orquesta extracción, validación, optimización e interpretación sin romper en ningún momento la separación de capas definida en CLAUDE.md:

```
START → extract_requirements
             │ is_complete=False → END  (pide clarificación al usuario)
             ↓ is_complete=True
        validate_normative
             │ errors → END  (devuelve errores normativos en alemán)
             ↓ ok=True
        invoke_solver          ← único nodo sin LLM; llama al CP-SAT
             │ INFEASIBLE/TIMEOUT/ERROR → handle_infeasible → END
             ↓ OPTIMAL/FEASIBLE
        interpret_result → END
```

Cada nodo tiene una responsabilidad única y no atraviesa la frontera LLM/geometría:
- `extract_requirements` — qwen2.5:7b extrae parámetros en JSON estructurado.
- `validate_normative` — qwen2.5:14b evalúa contra normativa urbanística simulada.
- `invoke_solver` — CP-SAT sin LLM; retorna `SolveLayoutOutput` validado por Pydantic.
- `interpret_result` — qwen2.5:7b genera la descripción en alemán para el usuario.
- `handle_infeasible` — lógica determinista; propone ajustes de tipología sin LLM.

### Herramientas (tools)

| Herramienta | Tipo | Propósito |
|---|---|---|
| `solve_layout` | Síncrona, CP-SAT | Optimización espacial completa |
| `query_regulation` | Síncrona, stub | Consulta normativa (preparada para RAG en Fase 6) |
| `suggest_typology_adjustments` | Síncrona, determinista | Propone ajustes cuando el solver no halla solución |
| `describe_solution` | Asíncrona, LLM | Genera texto en alemán desde la solución CP-SAT |
| `calculate_metrics` | Síncrona, Shapely | Métricas geométricas puras |
| `build_and_export_ifc` | Síncrona, IfcOpenShell | Generación de modelo BIM |

### Persistencia multi-turno

El grafo usa `MemorySaver` de LangGraph con `thread_id = "{project_id}-chat"`, lo que permite continuar la conversación entre peticiones HTTP dentro de una sesión de servidor. Cada proyecto tiene su propio hilo de memoria independiente.

### API de chat

Dos endpoints nuevos en `POST /api/projects/{id}/chat` y `WS /api/projects/{id}/chat/stream`:

- **POST**: invoca el grafo con `ainvoke`, devuelve `{response, thread_id, feasible, solution}`.
- **WebSocket**: usa `astream_events` (v2) para emitir un evento `node_start`/`node_end` por cada nodo activo y el resultado final en `done`. El cliente puede mostrar indicadores de progreso en tiempo real.

### UI de chat integrada en el frontend

Panel lateral fijo con toggle visible en todas las rutas de proyecto:

- Historial de mensajes con burbujas diferenciadas (usuario: terracota; asistente: blanco).
- Indicador de progreso con la etiqueta alemana del nodo activo ("Solver läuft…", "Normvorschriften werden geprüft…").
- Badge de factibilidad (verde/rojo) sobre la respuesta del asistente.
- Un WebSocket por mensaje (one-shot); el servidor cierra la conexión tras `done`/`error`.
- Enter para enviar, Shift+Enter para salto de línea.

### Modelo de datos de chat (frontend)

```typescript
ChatMessage   = { role, content, feasible?, solution? }
ChatNodeEvent = { type: 'node_start'|'node_end', node, label? }
ChatDoneEvent = { type: 'done', response, feasible, solution }
ChatErrorEvent = { type: 'error', message }
```

---

## Flujo de prueba manual

Prompt de referencia:

> **"Ich habe ein Grundstück von 20×30 Metern und möchte 10 Wohnungen mit zwei Schlafzimmern planen."**

Secuencia esperada:

1. Panel muestra "Anforderungen werden analysiert…" (~1-3 s, qwen2.5:7b).
2. Panel muestra "Normvorschriften werden geprüft…" (~3-8 s, qwen2.5:14b).
3. Panel muestra "Solver läuft…" (~1-5 s, CP-SAT).
4. Panel muestra "Antwort wird generiert…" (~1-3 s, qwen2.5:7b).
5. Respuesta en alemán con resumen de unidades colocadas, áreas y badge "Machbar".

---

## Benchmark de latencia

Ver script en `docs/progress/benchmark_chat.py`. Resultados orientativos medidos en hardware de desarrollo (Apple M2 Pro / NVIDIA RTX 3070, cuantización Q4_K_M):

| Modelo de extracción | Modelo de validación | Latencia media/turno (factible) | Latencia media/turno (infactible) |
|---|---|---|---|
| qwen2.5:7b (Q4_K_M) | qwen2.5:14b (Q4_K_M) | 12–20 s | 8–14 s |
| qwen2.5:7b (Q4_K_M) | qwen2.5:7b (Q4_K_M) | 8–14 s | 5–9 s |
| qwen2.5:14b (Q4_K_M) | qwen2.5:14b (Q4_K_M) | 20–35 s | 15–25 s |

La configuración por defecto (7b extractor + 14b validador) es el equilibrio calidad/latencia elegido. Ver ADR 0009.

Para ejecutar el benchmark con el backend activo:

```bash
cd docs/progress
python benchmark_chat.py --host http://localhost:8000 --project-id <ID>
```

---

## Limitaciones conocidas al cerrar Fase 5

- `MemorySaver` no persiste entre reinicios del servidor. Para persistencia real se necesita `AsyncSqliteSaver` o `AsyncPostgresSaver` (Fase 6+).
- La normativa en `query_regulation` es un stub con datos hardcoded. El RAG real queda para Fase 6.
- El WebSocket de chat no implementa reconexión automática (diseño one-shot intencional); si la red se interrumpe durante una ejecución larga el usuario debe reenviar el mensaje.
- El copiloto no lee ni modifica el proyecto persistido en base de datos; trabaja solo con los parámetros extraídos del texto en la sesión activa.

---

## Qué habilita Fase 6

- Sustituir el stub `query_regulation` por RAG real contra normativa urbanística indexada en Qdrant.
- Persistir el hilo de chat en PostgreSQL para recuperar el contexto entre sesiones.
- Conectar el resultado del copiloto directamente al flujo de generación (guardar versión desde el grafo).
- Mejorar la extracción con few-shot examples y evaluación automática de calidad de respuesta.
