# Testing Basado en Riesgo

## Objetivo

Priorizar las pruebas de mantenimiento de Cimiento v1.0 según impacto de negocio y probabilidad técnica, usando evidencia real del código y de la suite automatizada actual.

## Fuentes usadas

- `README.md`
- `docs/manual-usuario.md`
- `frontend/src/App.tsx`
- `frontend/src/features/chat/ChatPanel.tsx`
- `frontend/src/features/ifc-viewer/IfcModelWorkspace.tsx`
- `backend/src/cimiento/api/routers/projects.py`
- `backend/src/cimiento/api/routers/generation.py`
- `backend/src/cimiento/api/routers/renders.py`
- `backend/src/cimiento/api/routers/diffusion.py`
- `backend/tests/integration/test_api_endpoints.py`
- `backend/tests/unit/test_project_repository.py`
- `backend/tests/unit/test_vision_router.py`
- `frontend/src/pages/ProjectEditorPage.test.tsx`
- `frontend/src/pages/ProjectRendersPage.test.tsx`
- `frontend/src/features/chat/ChatPanel.test.tsx`
- `frontend/src/features/diffusion/DiffusionComposerDialog.test.tsx`
- `frontend/src/api/vision.test.ts`
- `frontend/src/App.test.tsx`

## Escala de riesgo

- Impacto: Alto, Medio, Bajo.
- Probabilidad: Alta, Media, Baja.
- Prioridad: combinación práctica de ambos factores para decidir qué probar primero.
- Riesgo residual: nivel que sigue abierto después de la cobertura automatizada actual.

## Evidencia ejecutada en esta revisión

Se ejecutaron estas pruebas focales:

```bash
cd backend && /home/miguel/cimiento/backend/.venv/bin/python -m pytest tests/integration/test_api_endpoints.py -k "generation_job_websocket_and_downloads or render_job_gallery_and_download_by_id or patch_program_creates_new_version_with_updated_floors or patch_solar_creates_new_version_with_updated_north_angle" -q
# 4 passed

cd backend && /home/miguel/cimiento/backend/.venv/bin/python -m pytest tests/unit/test_vision_router.py -q
# 8 passed

cd backend && /home/miguel/cimiento/backend/.venv/bin/python -m pytest tests/unit/test_project_repository.py -k "updated_at_changes or concurrent_version_creation" -q
# 3 passed

cd frontend && npm test -- --run src/pages/ProjectEditorPage.test.tsx src/pages/ProjectRendersPage.test.tsx src/features/chat/ChatPanel.test.tsx src/features/diffusion/DiffusionComposerDialog.test.tsx
# 15 passed
```

## Matriz de riesgos

| ID | Riesgo | Impacto | Probabilidad | Prioridad | Evidencia actual | Hueco principal | Riesgo residual |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 | Versionado inconsistente del proyecto, incluyendo `updated_at`, creación de versiones y concurrencia | Alto | Media | Alta | `backend/tests/unit/test_project_repository.py`; `backend/tests/integration/test_api_endpoints.py` | No hay prueba de concurrencia a nivel API, solo repositorio | Medio-bajo |
| R-02 | Generación asíncrona con pérdida de eventos, estados incorrectos o descargas incompletas | Alto | Media | Alta | `test_generation_job_websocket_and_downloads` en `backend/tests/integration/test_api_endpoints.py` | Falta prueba frontend del `ProjectGenerationPanel` y de reconexión real del stream | Medio |
| R-03 | Visor IFC usable de forma incorrecta: tab visible sin IFC, árbol roto, selección/proyección/cortes sin validar | Alto | Media | Alta | `frontend/src/pages/ProjectEditorPage.test.tsx` cubre el gating de la pestaña; backend valida descargas de outputs | No existen tests dedicados para `IfcModelWorkspace` ni `IfcViewer` | Alto |
| R-04 | Fuga de contexto conversacional entre proyectos o pérdida de continuidad del hilo | Medio-alto | Media | Media-alta | `frontend/src/features/chat/ChatPanel.test.tsx` cubre reset por proyecto y `thread_id` estable | No existen tests backend del WebSocket `/api/projects/{id}/chat/stream` | Medio |
| R-05 | Análisis visual aceptando entradas erróneas o reutilizándose sin revisión humana | Alto | Media | Alta | `backend/tests/unit/test_vision_router.py`; `frontend/src/api/vision.test.ts` | No hay tests UI del `PlanAnalyzerDialog` ni flujo end-to-end desde editor | Medio |
| R-06 | Render y difusión fallando por contratos de job, galería, imágenes de referencia o estados de conexión | Alto | Media | Alta | `test_render_job_gallery_and_download_by_id`; `frontend/src/pages/ProjectRendersPage.test.tsx`; `frontend/src/features/diffusion/DiffusionComposerDialog.test.tsx` | No hay tests backend específicos del endpoint de difusión ni smoke tests reales con Blender/GPU | Medio-alto |
| R-07 | Borrado o navegación del editor dejando caché inconsistente o rutas rotas | Medio | Baja | Media | `frontend/src/pages/ProjectEditorPage.test.tsx`; CRUD API en `backend/tests/integration/test_api_endpoints.py` | Cobertura suficiente para mantenimiento normal | Bajo |
| R-08 | Rutas principales de producto mal resueltas o idioma del documento incorrecto | Medio | Baja | Media-baja | `frontend/src/App.test.tsx` | No hay riesgo alto adicional en esta revisión | Bajo |

## Prioridad recomendada de nuevas pruebas

1. Añadir tests frontend de `ProjectGenerationPanel` con escenarios de reconexión, cierre y error del stream.
2. Añadir tests de `IfcModelWorkspace` para cambio de proyección, árbol, selección y paginación por planta.
3. Añadir tests backend del WebSocket de chat para confirmar contrato de eventos y manejo de `thread_id`.
4. Añadir tests backend del endpoint de difusión, hoy cubierto solo desde frontend con mocks.
5. Añadir tests UI del `PlanAnalyzerDialog` para cerrar la brecha entre API de visión y uso real en editor.
6. Crear smoke tests etiquetados para render y difusión reales sobre hardware soportado, separados de la suite rápida.

## Conclusión

La base más sensible del producto no está desprotegida: versionado, generación, render y visión tienen cobertura automatizada útil y han pasado en esta revisión. El mayor riesgo residual ya no está en el backend CRUD, sino en tres contratos de integración de alto valor que siguen sin prueba específica en frontend o end-to-end: generación por stream, visor IFC y flujo visual de plan analyzer.