# ADR 0012 — División OpenCV + VLM para ingesta visual de planos

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Cierre de Fase 7 — ingesta visual de planos arquitectónicos

---

## Contexto

Fase 7 introduce la capacidad de leer un plano escaneado (foto o escaneo de planta arquitectónica) y extraer de él información geométrica y semántica utilizable como entrada opcional al solver. El objetivo no es automatizar la conversión de plano a modelo BIM, sino **reducir el trabajo manual de entrada de datos** cuando el arquitecto ya tiene un plano existente.

El problema tiene dos dimensiones muy distintas:

1. **Geometría:** detectar líneas de muro, rectificar perspectiva, localizar regiones de texto. Estos problemas tienen soluciones deterministas clásicas.
2. **Semántica:** identificar si una abertura es puerta o ventana, leer etiquetas en alemán, clasificar una región como cocina o dormitorio. Estos problemas son contextuales y difíciles de resolver sin comprensión visual de alto nivel.

Concentrar ambas responsabilidades en un único componente (solo VLM o solo OpenCV) introduce compromisos inaceptables en al menos una de ellas.

---

## Decisión

Se divide la capa de visión en dos sublayers con responsabilidades distintas y sin solapamiento:

| Sublayer | Herramienta | Responsabilidad |
|---|---|---|
| `preprocessing.py` | OpenCV (HoughLinesP, umbralización adaptativa, warpPerspective) | Geometría: rectificación, normalización, detección de líneas, localización de regiones de texto |
| `interpreter.py` | VLM local (qwen2.5vl:7b vía OllamaClient) | Semántica: lectura de etiquetas, clasificación de estancias, identificación de símbolos |

La escala métrica (`meters_per_pixel`) se solicita también al VLM porque la lectura de barras de escala y cotas es una tarea semántica, no geométrica.

Ambas sublayers se fusionan en `combine_preprocessing_and_vlm`, que devuelve un `PlanInterpretation` con `review_required=True` de forma permanente.

---

## Alternativas descartadas

### Opción A — VLM puro (sin OpenCV)

Delegar todo al VLM: que extraiga líneas, detecte texto, clasifique rooms y estime escala desde la misma llamada.

**Por qué se descartó:**

- Los VLM multimodales locales (7B–13B parámetros) son poco fiables para extraer coordenadas precisas de segmentos geométricos. Cuando se les pide "dame las coordenadas en píxeles de las paredes", el output tiene alta varianza y coordenadas inventadas.
- Las llamadas al VLM son costosas en tiempo. Delegar también las tareas deterministas (que OpenCV resuelve en milisegundos) desperdicia latencia sin beneficio.
- El coste de una llamada al VLM para rectificar perspectiva es incongruente con la trivialidad geométrica de la tarea.

### Opción B — OpenCV puro con heurísticas avanzadas

Usar únicamente técnicas clásicas (morfología, detección de contornos, tesseract OCR, clasificadores tradicionales) sin LLM.

**Por qué se descartó:**

- La diversidad de estilos de plano (escalas, simbologías, tipografías, idiomas) hace que las heurísticas de clasificación funcional sean frágiles y difíciles de mantener.
- Tesseract sobre planos arquitectónicos con rotaciones y tipografía técnica tiene tasas de error inaceptables para alemán sin fine-tuning específico.
- La clasificación funcional de estancias requiere comprensión del contexto visual (mobiliario representado, proporción de la estancia, posición relativa) que las heurísticas geométricas no capturan bien.

### Opción C — Modelo dedicado de segmentación semántica de planos (CubiCasa5K, etc.)

Usar un modelo entrenado específicamente sobre datasets de planos arquitectónicos para segmentación pixel a pixel.

**Por qué se descartó:**

- Requiere dependencias adicionales pesadas (PyTorch, pesos específicos), contrarias al principio de mínimas dependencias backend.
- Los modelos disponibles están entrenados sobre planos con estilo homogéneo y no generalizan bien a planos escaneados informales.
- Introduce un modelo entrenado que no se puede correr con Ollama, rompiendo la arquitectura de inferencia local unificada.

---

## Limitaciones asumidas explícitamente

Estas limitaciones son conocidas y aceptadas en Fase 7. No son bugs; son consecuencias del enfoque:

1. **La geometría de los muros es imprecisa.** HoughLinesP detecta segmentos dominantes pero no reconstituye el grafo topológico de la planta. Muros oblicuos, curvas y elementos menores se pierden o distorsionan.

2. **Las coordenadas del VLM son aproximadas.** Cuando el VLM devuelve `bbox_px`, las coordenadas tienen un error de decenas de píxeles. No son aptas para cálculo geométrico directo; solo sirven como referencia visual de localización.

3. **La escala puede ser None.** Si el plano no incluye barra de escala legible, cotas numéricas o referencia dimensional reconocible por el VLM, `meters_per_pixel` es `None` y `draft_building` es `None`. El pipeline no inventa escala.

4. **`draft_building` siempre requiere revisión humana.** El objeto `Building` generado tiene `review_required=True` permanente. **No puede usarse como entrada directa del solver sin confirmación explícita del usuario.** Esto es una invariante arquitectónica, no una advertencia blanda.

5. **El rendimiento depende del modelo VLM disponible.** Con qwen2.5vl:7b en local, el pipeline completo tarda entre 30 y 90 segundos según el hardware. No es apto para uso en tiempo real.

6. **Un plano por llamada, una planta por plano.** La Fase 7 no maneja edificios de varias plantas ni composición de varios documentos. Cada llamada procesa exactamente una imagen y asume que representa una sola planta.

---

## Consecuencias

**Positivas:**

- Separación de responsabilidades limpia: OpenCV maneja lo determinista, el VLM maneja lo semántico.
- La capa de preprocessing es completamente testeable de forma unitaria sin necesidad de VLM.
- Cualquier mejora futura (mejor modelo VLM, pipeline OCR alternativo) afecta a su sublayer sin romper la otra.
- El `PlanInterpretation` como output tipado garantiza que el contrato con capas superiores esté definido en Pydantic.

**Negativas:**

- La pipeline completa requiere dos conjuntos de herramientas (OpenCV + Ollama) activos simultáneamente.
- El error de coordinadas del VLM no es corregible sin un segundo paso de refinamiento (fuera del scope de Fase 7).
- La separación en dos sublayers no elimina la latencia; la suma de llamadas VLM puede ser de 3–4 invocaciones por plano.

---

## Revisión

Revisar esta ADR si ocurre alguno de estos supuestos:

- Un modelo VLM local mejora suficientemente en extracción de coordenadas para reemplazar HoughLinesP con fiabilidad comparable.
- Se introduce un modelo de segmentación semántica de planos ejecutable con Ollama.
- La demanda de usuarios muestra que los planos recibidos son sistemáticamente de un único estilo (CAD exportado, BIM screenshot) que permite pipeline más especializado.
