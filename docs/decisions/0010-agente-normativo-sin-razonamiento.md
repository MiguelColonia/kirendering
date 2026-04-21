# ADR 0010 — El agente normativo no razona: solo recupera y cita

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Contexto:** Fase 6 — RAG normativo sobre GEG y MBO indexados en Qdrant

---

## Contexto

El copiloto necesita responder preguntas sobre normativa alemana de edificación (GEG, MBO, BauNVO, WoFlV, LBO). La alternativa obvia es instruir al LLM para que "razone sobre normativa" usando su conocimiento de preentrenamiento. Esta decisión documenta por qué esa alternativa fue descartada.

---

## Decisión

**El LLM normativo de Cimiento no razona ni asume sobre normativa. Solo recupera fragmentos del corpus indexado y los cita.**

Esto se implementa mediante tres mecanismos:

### 1. Aislamiento del contexto

El nodo `answer_with_regulation` entrega al LLM **únicamente** los artículos recuperados por el retriever RAG (`retrieve()` sobre Qdrant). El LLM no recibe ningún contexto que le permita "rellenar" información ausente con su conocimiento de preentrenamiento.

El prompt del sistema lo establece de forma explícita:

```
STRENGE REGELN — KEIN SPIELRAUM:
1. Du antwortest AUSSCHLIESSLICH auf Basis des dir übergebenen KONTEXTS.
2. Du darfst keinerlei eigenes Wissen, Schätzungen oder Annahmen einfließen lassen.
3. Wenn die Antwort nicht vollständig im bereitgestellten Kontext enthalten ist, antworte:
   "Diese Information liegt mir im bereitgestellten Kontext nicht vor."
```

### 2. Citas obligatorias por artículo

Cada afirmación que el LLM produzca debe ir acompañada de su fuente normativa en formato `[DOC §N]` (p.ej. `[GEG § 10]`, `[MBO § 37]`). Esto hace que cualquier alucinación sea inmediatamente detectable: si una cita no existe en el contexto entregado, el LLM la habrá inventado.

El formato es intencionalmente simple y computable: el `article_number` del `RegulationChunk` indexado coincide con el formato `§ N` que el LLM debe usar en las citas.

### 3. Respuesta de abstención predefinida

Si el retriever no devuelve artículos relevantes o el LLM no puede cubrir la pregunta con el contexto disponible, debe responder con un texto predefinido:

```
Diese Information liegt mir im bereitgestellten Kontext nicht vor.
Bitte konsultieren Sie die aktuelle Fassung der einschlägigen Rechtsnorm.
```

Esto prohíbe explícitamente la síntesis especulativa.

---

## Por qué no "razonamiento normativo" del LLM

### El problema del conocimiento desactualizado

Los LLMs de preentrenamiento aprenden normativa hasta su fecha de corte. GEG 2023 entró en vigor el 1 de enero de 2024; modelos entrenados antes la desconocen o la confunden con el GEG 2020. Las enmiendas a las LBO de los distintos Länder son frecuentes y no aparecen en los corpora de preentrenamiento estándar. Un LLM que "razona" sobre normativa puede citar artículos derogados o valores incorrectos con la misma confianza que citas correctas.

### La falta de trazabilidad destruye la confianza profesional

Un arquitecto que usa Cimiento necesita poder verificar cada requisito normativo citado. Un LLM que sintetiza normativa "de memoria" no proporciona la referencia exacta al texto legal; proporciona una paráfrasis que puede diferir del texto vigente. Esto es inaceptable en un contexto profesional donde la responsabilidad civil del técnico está en juego.

### Las alucinaciones normativas tienen consecuencias asimétricas

En generación de texto creativo, una alucinación es un error de calidad. En normativa de edificación, una alucinación puede resultar en un proyecto que no obtiene licencia, en obras que hay que demoler, o en responsabilidad del técnico proyectista. El coste de un falso positivo (el LLM afirma que algo es conforme cuando no lo es) supera con creces el coste de un falso negativo (el sistema dice que no tiene información).

### RAG + citas es verificable; razonamiento LLM no lo es

Cuando el retriever devuelve `[GEG § 10]` con el texto exacto del artículo, el arquitecto puede:
1. Contrastar el texto con la BOE o el Bundesgesetzblatt.
2. Ver la puntuación de similitud (`score`) para evaluar la relevancia.
3. Detectar si el chunk está desactualizado por fecha de indexación.

Cuando el LLM "razona" sobre normativa, el arquitecto no tiene ningún texto fuente que contrastar.

---

## Separación de responsabilidades en el grafo

| Nodo                      | Usa LLM | Usa RAG | Propósito                                         |
|---------------------------|---------|---------|---------------------------------------------------|
| `extract_requirements`    | Sí      | No      | Extraer parámetros de diseño del mensaje          |
| `validate_normative`      | Sí      | Sí      | Comprobar conformidad normativa de los parámetros |
| `invoke_solver`           | No      | No      | Optimización espacial CP-SAT (determinista)       |
| `interpret_result`        | Sí      | No      | Describir la solución en alemán                   |
| `handle_infeasible`       | No      | No      | Proponer ajustes al programa (determinista)       |
| **`answer_with_regulation`** | **Sí** | **Sí**  | **Responder consultas normativas directas con citas** |

El nodo `validate_normative` también usa RAG pero con propósito diferente: verifica conformidad (salida: JSON booleano). El nodo `answer_with_regulation` responde preguntas abiertas con el texto de los artículos recuperados (salida: prosa citada).

---

## Consecuencias

**Positivas:**
- Cero alucinaciones normativas en el corpus indexado.
- Trazabilidad completa: cada afirmación tiene una fuente verificable.
- Actualizable: re-indexar con una nueva versión del GEG actualiza automáticamente las respuestas.
- Testeable: los tests de fidelidad pueden verificar que el chunk correcto aparece en el prompt sin depender del comportamiento no determinista del LLM.

**Negativas:**
- El sistema solo puede responder preguntas cuya respuesta esté en el corpus indexado. Preguntas sobre normativa no indexada reciben la respuesta de abstención.
- El corpus debe mantenerse actualizado cuando se publiquen nuevas versiones de GEG, MBO o LBO. La re-indexación es un proceso manual.
- La calidad de la respuesta depende de la calidad del chunking y del embedding. Un artículo mal extraído producirá una cita con texto incorrecto aunque la referencia (`§ N`) sea correcta.

---

## Alternativas descartadas

| Alternativa | Por qué se descartó |
|-------------|---------------------|
| LLM razona directamente sobre normativa (sin RAG) | Conocimiento desactualizado, sin trazabilidad, alucinaciones inaceptables en contexto profesional |
| RAG sin instrucción de abstención | El LLM puede completar el contexto con conocimiento de preentrenamiento cuando el chunk recuperado es parcial |
| Reglas deterministas (lookup de tabla) | Cubre solo los valores indexados explícitamente; no responde preguntas semánticas ni recupera texto exacto de artículos complejos |
| Fine-tuning sobre corpus normativo | Coste de entrenamiento elevado, sin trazabilidad, requiere re-entrenamiento con cada actualización normativa |
