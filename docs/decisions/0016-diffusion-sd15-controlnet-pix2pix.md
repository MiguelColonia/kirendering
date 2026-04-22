# ADR 0016 — Pipeline de difusión: SD 1.5, ControlNet e InstructPix2Pix

**Estado:** Accepted  
**Fecha:** 2026-04-22  
**Decidido por:** Equipo Cimiento  

---

## Contexto

La fase 8 incorporó render fotorrealista mediante Blender Cycles (IFC → PNG determinista).
El resultado es estructuralmente perfecto pero estilísticamente fijo: Blender siempre
produce el mismo render dado el mismo IFC.

Se necesita una capa generativa que permita:

1. **Img2Img + ControlNet** — tomar cualquier imagen de entrada (foto de maqueta,
   boceto, render Blender) y transformarla en una visualización arquitectónica
   fotorrealista manteniendo la estructura exacta de la imagen original.
2. **InstructPix2Pix** — editar una imagen existente siguiendo instrucciones de texto
   ("cambia la fachada a hormigón visto", "añade vegetación en cubierta").

ADR-0014 ya decidió adoptar `diffusers` (HuggingFace) sobre ComfyUI como backbone
de inferencia. Este ADR fija el modelo base, los adaptadores y la estrategia de
carga para el hardware de referencia.

---

## Opciones consideradas

### Modelo base

| Opción | VRAM fp16 | Calidad | ControlNet | InstructPix2Pix |
|--------|----------|---------|------------|-----------------|
| SD 1.5 | ~4 GB | buena | nativa, bien documentada | `timbrooks/instruct-pix2pix` |
| SDXL base | ~6 GB | alta | modelos XL separados | no estable |
| SDXL Turbo | ~6 GB | alta-rápida | no oficial | no disponible |

**Decisión**: SD 1.5 (`runwayml/stable-diffusion-v1-5`).

Razones:
- InstructPix2Pix más estable es SD 1.5.
- ControlNet para SD 1.5 tiene el catálogo más amplio y probado.
- Cabe en 8 GB VRAM con fp16 dejando 2 GB de margen.
- SDXL es una migración futura desacoplada (cambiar `sd_base_model` en settings).

### Modos de control

| Modo | Preprocesador | Caso de uso |
|------|--------------|-------------|
| `img2img_controlnet_depth` | DPT-MiDaS (Intel/dpt-hybrid-midas) | Render Blender → SD preservando volúmenes |
| `img2img_controlnet_canny` | Canny (OpenCV, ya instalado) | Bocetos o planos → fotorrealismo |
| `instruct_pix2pix` | Ninguno | Edición semántica guiada por instrucción |

Fallback automático: si la estimación de profundidad falla (sin GPU o timeout),
el modo `depth` degrada silenciosamente a `canny` con aviso en `warnings`.

---

## Decisión

### Arquitectura del módulo

```
cimiento/diffusion/
  __init__.py          → re-exporta run_diffusion
  pipeline.py          → orquestador con caché lazy de pipelines
  preprocessors.py     → extract_canny, extract_depth
```

```
cimiento/schemas/
  diffusion.py         → DiffusionMode, DiffusionConfig, DiffusionResult
```

Los pipelines se cargan **bajo demanda** la primera vez que se usan y se mantienen
en un dict global (`_LOADED_PIPELINES`). El módulo no importa `torch` ni `diffusers`
en el nivel de módulo — los imports son internos a las funciones para que el
servidor arranque aunque `diffusers` no esté instalado.

### Modelos fijados en settings

```
sd_base_model                = "runwayml/stable-diffusion-v1-5"
sd_controlnet_depth_model    = "lllyasviel/sd-controlnet-depth"
sd_controlnet_canny_model    = "lllyasviel/sd-controlnet-canny"
sd_instruct_pix2pix_model    = "timbrooks/instruct-pix2pix"
sd_depth_estimator_model     = "Intel/dpt-hybrid-midas"
diffusion_steps              = 20
diffusion_timeout_seconds    = 600
hf_cache_dir                 = None   (opcional, configurable via .env)
```

### Detección de dispositivo

```
1. ¿torch.version.hip is not None?  → cuda (ROCm, RX 6600 con HSA_OVERRIDE_GFX_VERSION=10.3.0)
2. ¿torch.cuda.is_available()?       → cuda (NVIDIA)
3. Fallback                          → cpu (lento, advertencia en warnings)
```

### Integración con el sistema de jobs

Los jobs de difusión reutilizan `JobManager` (mismo patrón que renders):
- `POST /api/projects/{id}/diffusion` → devuelve `job_id`
- WebSocket `/api/jobs/{job_id}/stream` → eventos de progreso
- Resultado guardado como `GeneratedOutput(output_type="DIFFUSION")`
- Galería accesible via `GET /api/projects/{id}/diffusion`

### Resolución de imagen

Todos los modos redimensionan a **512×512** antes de procesar (óptimo SD 1.5).
El resultado se guarda como PNG sin reescalar. Si en el futuro se adopta SDXL,
la resolución óptima sería 1024×1024.

---

## Consecuencias

- ✅ Tres nuevas capacidades generativas sin dependencia de servicios cloud.
- ✅ AMD RX 6600 + ROCm compatible; fallback CPU garantizado.
- ✅ Lazy loading: el servidor arranca aunque `diffusers`/`torch` no estén instalados.
- ✅ Caché en memoria: segunda llamada al mismo modo es instantánea.
- ❌ Primera ejecución: ~4–5 GB de descarga de modelos HuggingFace.
- ❌ Calidad inferior a SDXL; migración posible cambiando `sd_base_model`.
- ⚠️ `_LOADED_PIPELINES` persiste en memoria indefinidamente; en producción con
  múltiples workers habría que coordinar la caché (Fase futura).

## Revisión

Revisar si migrar a SDXL cuando InstructPix2Pix para SDXL sea estable en diffusers.
