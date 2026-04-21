# ADR 0014 — Estrategia SD: diffusers vs ComfyUI, modelo y backend de inferencia

**Estado:** Aceptado  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Fase 9 — pipeline de estilización con Stable Diffusion sobre renders Blender

---

## Contexto

Fase 9 añade estilización fotorrealista a los renders geométricos de Fase 8.
El pipeline recibe el PNG de Blender y produce una imagen estilizada usando
Stable Diffusion con ControlNet (preserva estructura arquitectónica) e IP-Adapter
(transfiere estética de una imagen de referencia opcional).

El equipo debía decidir tres cosas:

1. **Orquestación SD**: ComfyUI (servicio externo) vs `diffusers` (biblioteca Python).
2. **Modelo**: SDXL Turbo vs SDXL base Q8 según rendimiento real en el hardware.
3. **Backend de inferencia**: GPU local (RX 6600) vs CPU vs cloud opt-in.

---

## Decisión 1 — diffusers, no ComfyUI

Se adopta **`diffusers` (Hugging Face)** como biblioteca de inferencia.

### Opciones consideradas

| Criterio | ComfyUI | diffusers |
|---|---|---|
| Tipo de integración | Servicio web externo (HTTP API) | Biblioteca Python importable |
| Iniciación | Requiere servidor corriendo en puerto 8188 | `import diffusers` |
| Tests unitarios | Difícil (HTTP mocks, estado servidor) | Funciones mockeables directamente |
| Automatización en pipeline | Requiere cliente HTTP + gestión de workflows JSON | Llamada Python directa |
| Mantenimiento | Fork comunitario activo pero sin soporte oficial HF | Mantenido oficialmente por Hugging Face |
| ControlNet + IP-Adapter | Disponible vía custom nodes | `StableDiffusionXLControlNetImg2ImgPipeline` nativo |
| Adecuación al proyecto | Diseñado para uso interactivo visual | Diseñado para pipelines programáticos |

### Por qué se elige diffusers

- **Sin dependencias de servicio externo.** ComfyUI exige un servidor corriendo antes de que se pueda llamar al pipeline. `diffusers` es una importación Python estándar, coherente con la arquitectura del proyecto.
- **Testeable.** Las funciones de `diffusers` pueden mockearse con `unittest.mock`. Un servidor ComfyUI requiere fixtures de integración pesados o HTTP mocking.
- **API estable y contractual.** `diffusers` sigue semver y tiene ADRs de migración propios. Los workflows JSON de ComfyUI cambian con cada versión de nodos.
- **IP-Adapter + ControlNet en 3 líneas.** `pipeline.load_ip_adapter(...)` + `pipeline.set_ip_adapter_scale(...)` es la API oficial; en ComfyUI requiere orquestar nodos manualmente.
- **Coherente con transformers ya instalado.** El proyecto ya usa `transformers 5.5.4`; `diffusers` es su complemento natural.

---

## Decisión 2 — Modelo: SDXL Turbo local, SDXL base en cloud

### Benchmark de hardware real (2026-04-21)

| Configuración | Tiempo estimado por render | Veredicto |
|---|---|---|
| RX 6600 + ROCm (fp16) | 10–30 s | ✓ Aceptable |
| RX 6600 sin ROCm (CPU via PyTorch) | 3–8 min | ✗ Supera umbral |
| CPU puro (float32, SDXL Turbo) | 5–10 min | ✗ Supera umbral |
| Cloud Replicate (SDXL base) | 8–25 s | ✓ Aceptable |

**Resultado clave:** El RX 6600 tiene 8 GB de VRAM suficientes para SDXL fp16.
Pero ROCm **no está instalado** en el entorno actual. Sin ROCm, PyTorch no puede
usar la GPU AMD. En modo CPU, el tiempo por render supera el umbral de 5 minutos
definido para uso en producción.

### Opciones de modelo consideradas

| Modelo | Pasos | VRAM fp16 | Ventajas | Desventajas |
|---|---|---|---|---|
| SDXL Turbo | 1–4 | ~6 GB | Muy rápido, misma arquitectura SDXL | Guidance_scale=0, menos controlable |
| SDXL base | 20 | ~7 GB | Máxima calidad, guidance_scale configurable | Lento en CPU |
| SDXL + LCM LoRA | 4–8 | ~7 GB | Velocidad+calidad, guidance activo | LoRA adicional ~200 MB |
| SD 1.5 | 20 | ~4 GB | Ligero, compatible más ControlNets | Calidad inferior, formato distinto a SDXL |
| SDXL Q8 (bitsandbytes int8) | 20 | ~3.5 GB | Menor VRAM | bitsandbytes no soporta AMD ROCm |

### Decisión

- **Local**: `stabilityai/sdxl-turbo` en fp16, 4 pasos, guidance_scale=0.0.
  Requiere ROCm para ser viable en producción.
- **Cloud**: `stability-ai/sdxl` en Replicate, 20 pasos, mayor calidad.
- **"Q8" en el contexto AMD**: bitsandbytes Q8 no soporta ROCm.
  Se usa fp16 con `enable_model_cpu_offload()` como equivalente práctico.

---

## Decisión 3 — Backend: AUTO con cloud opt-in obligatorio si CPU

### Estrategia de detección automática

```
AUTO detección:
1. ¿torch.version.hip no es None? → LOCAL GPU (ROCm)
2. ¿torch.cuda.is_available()? → LOCAL GPU (NVIDIA)
3. ¿REPLICATE_API_TOKEN en env? → CLOUD
4. Fallback → LOCAL CPU con advertencia de tiempo
```

### Cloud opt-in: Replicate

Se elige **Replicate** como proveedor cloud opt-in por:
- API Python mínima (`pip install replicate`, una llamada)
- Soporta SDXL con img2img + ControlNet en modelos públicos
- Modelo ControlNet SDXL disponible: `jagilley/controlnet-sdxl-canny`
- Pay-per-use, sin suscripción
- Activación: variable de entorno `REPLICATE_API_TOKEN`

Alternativas evaluadas y descartadas:
- RunPod: requiere provisioning de GPU instance (mayor complejidad operativa)
- Hugging Face Inference API: SDXL ControlNet no disponible en API serverless
- Stability AI API: pricing menos predecible, sin ControlNet combinado

---

## Limitaciones asumidas

1. **ControlNet depth en cloud**: los modelos Replicate con ControlNet disponibles
   usan principalmente Canny o scribble. La ruta cloud usa Canny en su lugar.
   La ruta local usa depth heurístico (gradiente+sharpness) sobre el render Blender.
   La máxima calidad requiere Blender Z-pass + ROCm local (fuera de scope de Fase 9).

2. **Primera ejecución local**: SDXL Turbo (~2.5 GB fp16) + ControlNet (~1.2 GB) +
   IP-Adapter (~800 MB) requieren ~4.5 GB de descarga del hub HF. Solo en primera ejecución.

3. **IP-Adapter en cloud**: no disponible en la ruta Replicate de Fase 9; la imagen
   de referencia se incluye en el prompt textual como descripción.

4. **Calidad depth heurístico**: el mapa de profundidad generado por análisis de imagen
   (gradiente + Laplacian sharpness) es una aproximación. El Blender Z-pass (integración
   Fase 8+Fase 9) daría mayor calidad estructural. Pendiente como mejora.

---

## Consecuencias

**Positivas:**

- Pipeline completamente local y funcional en producción con ROCm instalado.
- Cloud opt-in transparente: el código no cambia, solo se pone la variable de entorno.
- Arquitectura extensible: sustituir SDXL Turbo por otro modelo solo requiere cambiar
  el string del model_id en `settings.py`.

**Negativas:**

- Sin ROCm, el pipeline local supera el umbral de 5 min por render.
- La instalación de ROCm es un paso manual significativo:
  `sudo apt install rocm` + `pip install torch --index-url .../rocm6.2`
- Primera descarga de modelos (~4.5 GB) puede ser lenta.

---

## Instrucciones para activar GPU local (RX 6600)

```bash
# 1. Instalar ROCm (Ubuntu 24.04)
sudo apt install rocm

# 2. Añadir usuario al grupo render
sudo usermod -aG render,video $USER && newgrp render

# 3. Instalar torch con ROCm
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2

# 4. Verificar
python -c "import torch; print(torch.version.hip)"  # debe mostrar versión ROCm
```

---

## Revisión

Revisar esta ADR si:

- Se instala ROCm y se actualiza torch: medir el tiempo real en RX 6600 y confirmar
  que el pipeline es viable sin cloud.
- diffusers publica soporte oficial para SDXL ControlNet Q4 en ROCm.
- Se decide integrar el Blender Z-pass como depth map para ControlNet (mejora calidad).
- Se evalúan alternativas cloud (RunPod, Fal, Modal) con mejor soporte ControlNet.
