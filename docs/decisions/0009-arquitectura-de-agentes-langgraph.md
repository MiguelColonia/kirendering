# ADR 0009 — Arquitectura de agentes: LangGraph, nodos y asignación de modelos por rol

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Diseño del copiloto conversacional de Fase 5.

---

## Contexto

Fase 5 introduce la capa conversacional del copiloto. El sistema ya cuenta con un solver CP-SAT probado, una capa BIM funcional y una API REST+WebSocket. La nueva capa debe:

1. Extraer intención del usuario en lenguaje natural (alemán y español).
2. Validar los parámetros extraídos contra normativa urbanística.
3. Invocar el solver CP-SAT existente con inputs validados por Pydantic.
4. Interpretar y comunicar el resultado al usuario en alemán.
5. Proponer alternativas cuando el solver no encuentre solución.

Las decisiones clave son tres: **qué orquestador usar**, **cómo descomponer el flujo en nodos** y **qué modelo asignar a cada rol**.

---

## Decisión 1 — Orquestador: LangGraph sobre alternativas

### Opciones consideradas

**A. LangChain chains + LCEL**

- Encadenamiento lineal de llamadas LLM mediante objetos `Runnable`.
- Simple para flujos sin bifurcaciones.
- Sin persistencia de estado multi-turno nativa.
- Enrutamiento condicional verboso y poco explícito.

**B. Código Python puro (funciones async)**

- Mínima dependencia externa.
- Sin grafo explícito: el flujo es implícito en el código.
- Difícil de extender, visualizar y testear por nodo.
- Persistencia multi-turno requiere implementación manual.

**C. LangGraph `StateGraph` (elegida)**

- Grafo explícito con estado compartido tipado (`TypedDict`).
- Enrutamiento condicional declarativo y auditable.
- Persistencia multi-turno con `MemorySaver`/`AsyncSqliteSaver` sin código adicional.
- Streaming nativo por nodo mediante `astream_events` (v2).
- Visualizable para depuración; cada nodo es una función async independiente y testeable.

**Por qué LangGraph y no las alternativas:**

- El flujo del copiloto tiene bifurcaciones reales (¿hay suficiente info? ¿cumple normativa? ¿es factible?). LCEL las resuelve mal. Código puro las hace implícitas y frágiles.
- La persistencia multi-turno es un requisito desde el inicio. LangGraph la provee con una línea (`checkpointer=MemorySaver()`).
- El streaming por nodo permite al frontend mostrar indicadores de progreso específicos ("Solver läuft…") sin instrumentación adicional.
- El `StateGraph` con `TypedDict` fuerza un contrato explícito del estado compartido, coherente con la política de Pydantic del proyecto.

---

## Decisión 2 — Descomposición en cinco nodos

El grafo podría implementarse como un único nodo "LLM orquesta todo" o como múltiples nodos especializados. Se elige **cinco nodos con responsabilidades no solapadas**.

### Por qué no un único nodo

- Un único nodo LLM que razone sobre todo viola el principio fundamental de CLAUDE.md: el LLM nunca resuelve geometría ni invoca directamente el solver.
- Impide el streaming de progreso por etapa.
- Hace imposible sustituir individualmente la lógica de validación (p.ej., por RAG en Fase 6) sin reescribir el orquestador.
- El debugging de un fallo de extracción queda mezclado con el de validación y resolución.

### Por qué estos cinco nodos

| Nodo | Responsabilidad | ¿Usa LLM? | Modelo |
|---|---|---|---|
| `extract_requirements` | Extrae parámetros de diseño del texto del usuario en JSON | Sí | qwen2.5:7b |
| `validate_normative` | Evalúa cumplimiento normativo | Sí | qwen2.5:14b |
| `invoke_solver` | Llama al CP-SAT con inputs Pydantic | **No** | — |
| `interpret_result` | Genera descripción en alemán de la solución | Sí | qwen2.5:7b |
| `handle_infeasible` | Propone ajustes deterministas al programa | **No** | — |

La separación respeta que dos de los cinco nodos no usan LLM en absoluto: la geometría y la lógica determinista quedan completamente fuera del alcance del modelo.

### Flujo de enrutamiento condicional

```
START → extract_requirements
    is_complete=False → END            # Pide datos faltantes
    is_complete=True  → validate_normative
        errors → END                   # Informa bloqueo normativo
        ok     → invoke_solver
            INFEASIBLE/TIMEOUT/ERROR → handle_infeasible → END
            OPTIMAL/FEASIBLE         → interpret_result  → END
```

Cada condicional opera sobre el estado Pydantic del nodo anterior, no sobre texto libre.

---

## Decisión 3 — Asignación de modelos por rol

### Roles definidos en `config.py`

| Rol | Modelo | Parámetros | Cuantización |
|---|---|---|---|
| `extractor` | qwen2.5:7b-instruct | 7 B | Q4_K_M |
| `normative` | qwen2.5:14b-instruct | 14 B | Q4_K_M |
| `chat` | qwen2.5:7b-instruct | 7 B | Q4_K_M |
| `coder` | qwen2.5-coder:7b-instruct | 7 B | Q4_K_M |
| `embed` | nomic-embed-text | — | — |

### Por qué qwen2.5 y no LLaMA, Mistral u otros

- La familia `qwen2.5-instruct` es la que mejor sigue instrucciones en alemán y español en los benchmarks locales relevantes para esta tarea (multilingual instruction following).
- Soporte nativo de `response_format=json_schema` en Ollama, necesario para la extracción estructurada.
- La variante `coder` del mismo stack cubre la generación de código sin añadir otra familia de modelos.
- Un único proveedor de modelos (Qwen2.5) reduce la superficie de incompatibilidades de formato y cuantización.

### Por qué 7b para extracción e interpretación

La extracción de parámetros (`extract_requirements`) es una tarea de slot-filling sobre un schema JSON fijo: solar_width, solar_height, num_floors, typologies. Un modelo de 7B con instrucciones claras y `format=json` lo resuelve con alta fiabilidad y en ~1-3 segundos, frente a ~5-10 segundos del 14B.

La interpretación (`interpret_result`) genera texto descriptivo en alemán a partir de métricas ya calculadas (no razonamiento). La latencia importa aquí porque el usuario ya ha esperado la ejecución del solver; 7B es suficiente para producir texto fluido y correcto.

### Por qué 14b para validación normativa

La validación normativa (`validate_normative`) es la tarea de mayor exigencia de razonamiento del grafo:

- Recibe múltiples restricciones normativas en formato libre.
- Debe detectar conflictos no triviales (p.ej., altura implícita = num_floors × floor_height_m vs. límite CTE).
- Produce tanto una evaluación booleana (ok/errors) como una explicación en alemán para el usuario.
- Un error aquí bloquea el flujo completo, por lo que la precisión prima sobre la latencia.

El 14B reduce la tasa de falsos positivos (bloqueos injustificados) y falsos negativos (validaciones incorrectas aprobadas) de forma mensurable respecto al 7B en este tipo de razonamiento multi-restricción.

### Latencia media por turno (referencia)

| Configuración | Latencia media (factible) | Latencia media (infactible) |
|---|---|---|
| 7b extractor + 14b validador (por defecto) | 12–20 s | 8–14 s |
| 7b extractor + 7b validador | 8–14 s | 5–9 s |
| 14b extractor + 14b validador | 20–35 s | 15–25 s |

La configuración por defecto es el equilibrio elegido. Se puede bajar a "7b+7b" si la latencia es inaceptable en el hardware disponible ajustando `OLLAMA_MODEL_NORMATIVE` en el entorno.

---

## Consecuencias

- El grafo es extensible por nodo: Fase 6 puede sustituir `query_regulation` por RAG real sin tocar el resto.
- Cada nodo es testeable de forma aislada pasando un `OllamaClient` mock.
- El streaming por nodo ya está disponible para la UI sin trabajo adicional de instrumentación.
- La política de modelos está centralizada en `config.py` y se puede sobreescribir por entorno, sin tocar el código del grafo.
- La memoria multi-turno con `MemorySaver` no persiste entre reinicios del servidor. Para producción se deberá migrar a `AsyncSqliteSaver` o `AsyncPostgresSaver`.

---

## Revisión

Revisar esta ADR si:

- La validación normativa pasa de un stub a RAG real (Fase 6): evaluar si el 14B sigue siendo necesario con contexto recuperado.
- La latencia media supera 30 s en hardware de producción: considerar cuantización más agresiva (Q3_K_M) o el paso a qwen2.5:7b en todos los roles.
- LangGraph publica una versión con breaking changes en la API de `astream_events`.
- Se incorpora un tercer proveedor de modelos además de Ollama.
