# ADR 0013 — Modelo VLM local: qwen2.5vl:7b para interpretación de planos

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Cierre de Fase 7 — selección de modelo VLM para ingesta visual

---

## Contexto

La capa de visión (ADR 0012) necesita un modelo de lenguaje visual (VLM) capaz de:

1. Leer texto en alemán sobre planos arquitectónicos (etiquetas de estancias, cotas).
2. Clasificar regiones como tipos funcionales (Wohnzimmer, Küche, Bad, etc.).
3. Identificar símbolos arquitectónicos (puertas, ventanas, escaleras, columnas).
4. Estimar la escala métrica desde referencias visuales del propio plano.

El modelo debe funcionar en local con Ollama, sin llamadas a servicios cloud, y ser ejecutable en el hardware habitual de un arquitecto (16–32 GB RAM, GPU opcional).

La selección de modelo es complementaria a ADR 0002 (que decidió usar qwen2:7b para el agente conversacional). Los VLM son una familia distinta de modelos.

---

## Decisión

Se adopta **`qwen2.5vl:7b`** (Qwen2.5-VL-7B-Instruct) como modelo VLM local para la capa de visión, servido vía Ollama con el rol `"vision"` definido en `OllamaClient`.

---

## Alternativas consideradas

| Modelo | Parámetros | Multimodal real | Alemán | Ejecutable en Ollama | Observaciones |
|---|---|---|---|---|---|
| `qwen2.5vl:7b` | 7B | Sí | Bueno | Sí (nativo) | Baseline elegido |
| `llava:13b` | 13B | Sí | Limitado | Sí | Peor en alemán; más pesado |
| `llava:7b` | 7B | Sí | Limitado | Sí | Comprensión semántica inferior a qwen2.5vl |
| `minicpm-v:8b` | 8B | Sí | Moderado | Sí | Menos testeado en dominio arquitectónico |
| `bakllava:7b` | 7B | Sí | Débil | Sí | Alemán muy limitado; no adecuado |
| Modelos cloud (GPT-4V, Claude 3.5) | — | Sí | Excelente | No | Rompe el principio de operación local |

---

## Por qué qwen2.5vl:7b

### 1. Comprensión multimodal de calidad superior en la gama 7B

Qwen2.5-VL mejora sustancialmente sobre LLaVA y su versión anterior (Qwen-VL) en tareas de lectura de texto sobre imagen, comprensión de documentos y descripción espacial de objetos. En evaluaciones comparativas públicas (MMBench, OCRBench, DocVQA) supera a alternativas de tamaño equivalente o superior.

### 2. Soporte nativo de alemán

Los planos gestionados en Cimiento están etiquetados en alemán. Qwen2.5 fue entrenado con datos multilínge de alta calidad; su comprensión del alemán técnico-arquitectónico es notablemente mejor que la de los modelos LLaVA basados en Vicuna/Mistral.

### 3. Capacidad de lectura de documentos y texto superpuesto

La arquitectura nativa de Qwen2.5-VL (ventana dinámica de tokens visuales, rope 2D posicional) es especialmente eficaz en tareas de OCR sobre documentos, donde el texto aparece sobre fondos complejos, con rotación y en múltiples tamaños. Los planos arquitectónicos son esencialmente documentos de este tipo.

### 4. Integración con Ollama sin modificaciones

qwen2.5vl:7b está disponible en el registry de Ollama. La integración con `OllamaClient` ya existente (Fase 5) requiere únicamente añadir el rol `"vision"` en la configuración de modelos por rol, sin cambios en la infraestructura.

### 5. Hardware ejecutable

El modelo quantizado (Q4_K_M, ~4.7 GB) corre en CPU con 16 GB de RAM en tiempos aceptables para el caso de uso (30–90 s por plano, uso no interactivo). Con GPU de 8 GB VRAM mejora a 10–20 s. No requiere hardware especializado.

---

## Limitaciones asumidas del modelo

1. **Las coordenadas en píxeles son estimaciones, no medidas.** Qwen2.5-VL, como todo VLM generativo, no tiene acceso directo al espacio de píxeles. Las coordenadas que devuelve (`bbox_px`) son aproximaciones con error variable, típicamente de ±20–60 px sobre imágenes de 1000–2000 px de ancho. Por eso OpenCV (HoughLinesP) se mantiene como capa geométrica independiente.

2. **La confianza declarada no está calibrada.** El campo `confidence` que se pide al modelo en los prompts es subjetivo. No debe interpretarse como probabilidad estadística. Un `confidence: 0.9` del VLM no equivale a 90% de precisión medida.

3. **Planos con tipografías inusuales o manuscritas pueden fallar.** El modelo generaliza bien sobre planos CAD impresos y escaneos de media-alta calidad. Planos con escritura a mano o tipografías muy degradadas por el escaneo pueden producir resultados pobres.

4. **El modelo no tiene memoria entre llamadas del mismo pipeline.** Cada llamada (`identify_symbols`, `read_labels`, `estimate_room_types`) es independiente. Si el mismo plano produce resultados inconsistentes entre llamadas, no hay mecanismo de coherencia interna en Fase 7.

5. **Sin fine-tuning en dominio.** El modelo no ha sido ajustado específicamente sobre planos de edificios residenciales alemanes. La calidad de clasificación de estancias poco comunes (p. ej. `Hauswirtschaftsraum`) puede ser inferior a la de tipos canónicos.

---

## Consecuencias

**Positivas:**

- Un único modelo cubre lectura de texto, clasificación funcional, detección de símbolos y estimación de escala, reduciendo la complejidad operativa.
- La configuración por rol de `OllamaClient` permite sustituir el modelo VLM sin cambios en el código de la capa de visión.
- El rendimiento en CPU es suficiente para el caso de uso (carga de plano por el arquitecto, no procesamiento en batch ni tiempo real).

**Negativas:**

- El modelo añade ~4.7 GB de peso descargable adicional al entorno Ollama.
- La latencia total del pipeline (3–4 llamadas VLM) es de 30–90 s, inaceptable si se quisiera usar de forma interactiva. Esto es una limitación asumida de Fase 7.
- La varianza en la calidad del output depende de la calidad del plano de entrada y no es predecible sin ejecutar el modelo.

---

## Revisión

Revisar esta ADR si:

- Aparece un modelo VLM local de tamaño similar con mejor rendimiento demostrado en tareas de OCR sobre planos y soporte nativo de alemán.
- Se decide hacer fine-tuning del VLM sobre un dataset de planos residenciales alemanes.
- Ollama deja de soportar qwen2.5vl o lo sustituye por una versión incompatible que requiera cambios en los prompts.
- Se introduce un modelo de extracción de coordenadas de mayor precisión que permita eliminar la dependencia de OpenCV para geometría.
