# Fase 8 — Render fotorrealista

**Estado:** Completada  
**Fecha:** 2026-04-21

---

## Qué se logró

### Pipeline Blender headless a partir del IFC canónico

La fase cierra la cadena visual del producto sin romper la arquitectura del proyecto:

- El render parte siempre del IFC canónico generado por solver + geometría + BIM.
- `backend/src/cimiento/render/blender_pipeline.py` extrae geometría IFC, calcula cámaras automáticas y lanza Blender en modo headless.
- El script `backend/scripts/test_render_manual.py` permite validar el pipeline base sin pasar por la UI.
- El render no modifica el modelo BIM; solo genera salidas visuales derivadas.

Esto consolida el principio arquitectónico de Cimiento: el IFC es la fuente de verdad y el render es una materialización visual posterior.

### Integración SDXL + ControlNet para estilización fotorrealista

La capa de render queda definida como pipeline híbrido:

- Blender genera los pases geométricos y la base visual consistente con el modelo.
- SDXL / SDXL Turbo aporta la estilización final.
- ControlNet preserva la estructura arquitectónica del edificio durante la generación.
- La imagen de referencia opcional permite orientar la estética de materiales, luz y atmósfera.

La decisión técnica consolidada para esta parte queda documentada en el ADR 0014, que fija la dirección del stack de inferencia, los modelos objetivo y las alternativas aceptadas para hardware local o fallback controlado.

### UI de galería de renders en frontend

La interfaz web incorpora ya una vista específica para renders por proyecto:

- Ruta dedicada `/projekte/:id/renders`.
- Galería cronológica de renders generados.
- Botón **"Neuer Render"** con formulario en alemán.
- Selección de vista exterior/interior.
- Prompt opcional en alemán.
- Imagen de referencia opcional.
- Barra de progreso con estimación temporal.
- Descarga del render en alta calidad desde la propia galería.

Con esta fase, el producto deja de terminar en IFC/planos y añade una salida visual de presentación útil para revisión interna y comunicación con cliente.

---

## Limitaciones conocidas al cerrar Fase 8

- El tiempo por render sigue siendo incompatible con tiempo real; el objetivo operativo es del orden de 1 a 2 minutos por imagen en hardware razonable, pero puede empeorar de forma notable en CPU o GPUs con poca VRAM.
- La calidad visual final depende de la aceleración disponible, de la memoria gráfica y del modelo SDXL efectivo que pueda cargarse sin offloading excesivo.
- En hardware AMD, la viabilidad práctica depende de ROCm o de un fallback Vulkan suficientemente estable; la variabilidad entre drivers y distribuciones Linux sigue siendo un factor real.
- La calidad del resultado puede variar de forma apreciable entre máquinas incluso con el mismo prompt, sobre todo cuando entran en juego rutas fallback o límites de memoria.
- La referencia estética ayuda a orientar la imagen, pero no sustituye dirección artística humana ni revisión arquitectónica.

---

## Verificación manual

### Verificación desde la UI

1. Levantar backend y frontend.
2. Abrir un proyecto que ya tenga IFC generado.
3. Ir a `/projekte/<id>/renders`.
4. Pulsar **"Neuer Render"**.
5. Elegir `Außenansicht` o `Innenansicht`.
6. Añadir, si se desea, un prompt en alemán y una imagen de referencia.
7. Lanzar el render.

Resultado esperado:

- aparece un job activo con barra de progreso y estimación temporal,
- la vista se añade a la galería al finalizar,
- el render puede abrirse y descargarse en alta calidad,
- el proyecto mantiene intactos su IFC y sus exports BIM.

### Verificación del pipeline base por script

```bash
cd backend
uv run python scripts/test_render_manual.py --ifc data/outputs/rectangular_simple.ifc --samples 64 --device AUTO
```

Resultado esperado:

- Blender se ejecuta en modo headless sin abrir interfaz gráfica.
- La consola informa de dispositivo usado, tiempo total y vistas generadas.
- Los PNG se escriben en `backend/data/outputs/renders/test_render_manual/`.

---

## Qué habilita el cierre de v1.0

- Demostraciones de producto completas: desde proyecto y normativa hasta imagen final.
- Material comercial y técnico basado en renders reales del modelo BIM.
- Base operativa para optimización futura de tiempos, fidelidad visual y soporte multi-hardware sin reabrir la arquitectura principal.

---

## Fecha de cierre

Fase 8 cerrada el **2026-04-21**.