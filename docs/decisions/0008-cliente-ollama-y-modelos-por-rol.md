# ADR 0008 — Cliente Ollama y modelos por rol

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Decidido por:** Equipo Cimiento  
**Contexto:** Inicio de Fase 5 con infraestructura base para la capa conversacional.

---

## Contexto

El arranque de Fase 5 necesitaba una integración con Ollama que cumpliera varias condiciones a la vez:

- ser usable desde agentes y grafos sin acoplar la capa LLM a FastAPI,
- permitir elegir modelos distintos según el rol lógico del agente,
- soportar salida estructurada (`response_format=json_schema`) y tool-calling,
- ser fácil de testear en local con mocks ligeros,
- mantener la puerta abierta a usar LangGraph y, si conviene más adelante, LangChain por encima.

Además, el proyecto ya había fijado en `CLAUDE.md` una política explícita de modelos locales:

- `qwen2.5:14b-instruct-q4_K_M` para razonamiento crítico,
- `qwen2.5:7b-instruct-q4_K_M` para tareas rápidas y extracción,
- `qwen2.5-coder:7b-instruct-q4_K_M` para generación de código,
- `nomic-embed-text` para embeddings.

La decisión no era solo “cómo llamar a Ollama”, sino también dónde viviría la lógica de resolución de modelo y cuál sería el contrato estable para el resto de la capa LLM.

---

## Opciones consideradas

### Opción A — Usar `ChatOllama` o primitivas LangChain directamente en cada agente

**Ventajas:**

- Integración inmediata con ecosistema LangChain/LangGraph.
- Menos código propio al principio.

**Desventajas:**

- Mezcla la elección de modelo y el detalle del proveedor dentro de cada agente.
- Hace más costoso testear sin mocks más pesados o sin depender de abstracciones de terceros.
- Dificulta mantener un contrato pequeño y explícito para structured output y tools.

### Opción B — Usar el SDK Python de `ollama` como dependencia principal

**Ventajas:**

- Cliente dedicado al proveedor.
- API relativamente directa para el caso básico.

**Desventajas:**

- Sigue dejando sin resolver una abstracción propia para el resto del sistema.
- Añade otra superficie de API cuando `httpx` ya existe en el proyecto.
- El testeo y la instrumentación siguen requiriendo una capa interna adicional.

### Opción C — Crear un wrapper async propio sobre la API HTTP de Ollama con `httpx` (elegida)

**Ventajas:**

- Mantiene un contrato pequeño, explícito y desacoplado del framework web.
- Centraliza la selección de modelo en `model_for_role`.
- Facilita tests rápidos con un mock HTTP local muy ligero.
- Permite mapear `response_format=json_schema` y `tools` sin exponer detalles del proveedor al resto de módulos.

**Desventajas:**

- Obliga a mantener una capa propia de traducción de payloads.
- No aporta de serie utilidades de alto nivel como streaming avanzado o callbacks de tracing.
- Puede requerir adaptación futura si LangGraph necesita primitivas más ricas.

---

## Decisión

Se adopta la **Opción C**: un cliente propio `OllamaClient` en `backend/src/cimiento/llm/client.py`, implementado sobre `httpx.AsyncClient`, con estas responsabilidades explícitas:

- `model_for_role(role)` para resolver el modelo según el rol del agente,
- `chat(messages, role, format=None, tools=None)` como contrato mínimo estable,
- soporte inicial para `response_format=json_schema`,
- superficie de test limpia mediante un mock HTTP local.

La política de modelos queda centralizada en la configuración del backend y alineada con la estrategia ya documentada del proyecto.

---

## Consecuencias

- El resto de la capa LLM puede depender de un contrato pequeño y estable, no del proveedor concreto.
- Los agentes futuros podrán reutilizar el mapeo de modelos sin duplicar decisiones en cada módulo.
- Los tests de integración del cliente no dependen de Ollama real para la mayor parte de los casos.
- Se acepta como deuda que el cliente todavía no cubre streaming, retries avanzados, observabilidad detallada ni wrappers de tool-calling de más alto nivel.

---

## Revisión

Revisar esta ADR si ocurre alguna de estas condiciones:

- LangGraph exige capacidades que justifiquen adoptar una abstracción más alta de LangChain como capa principal.
- Se incorpora streaming como requisito del copiloto conversacional.
- La política de modelos por rol deja de ser suficiente y pasa a requerir selección dinámica por coste, latencia o contexto.
- Se decide soportar proveedores adicionales además de Ollama.