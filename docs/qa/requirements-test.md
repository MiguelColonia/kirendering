# Requirements-Based Test

## Objetivo

Trazar los requisitos visibles de Cimiento v1.0 contra evidencia automatizada existente para distinguir entre requisitos cubiertos, cubiertos parcialmente y huecos pendientes.

## Criterio usado

- `Cubierto`: existe evidencia automatizada directa del comportamiento principal.
- `Parcial`: existe cobertura de API, componente o contrato, pero no del flujo completo.
- `Hueco`: no se ha encontrado prueba automatizada específica del requisito.

## Matriz de trazabilidad

| ID | Requisito observable | Fuente principal | Evidencia automatizada | Estado | Observación |
| --- | --- | --- | --- | --- | --- |
| REQ-01 | El sistema debe permitir crear un proyecto con `Grundstück` y `Programm` iniciales, generando una versión útil desde el primer guardado | `README.md`, `docs/manual-usuario.md`, `backend/src/cimiento/api/routers/projects.py` | `test_projects_crud_flow` en `backend/tests/integration/test_api_endpoints.py`; `test_create_project_and_version_roundtrip` en `backend/tests/unit/test_project_repository.py` | Cubierto | La creación inicial queda validada tanto a nivel API como repositorio |
| REQ-02 | El sistema debe listar, consultar, actualizar y borrar proyectos | `backend/src/cimiento/api/routers/projects.py` | `test_projects_crud_flow`; borrado en `frontend/src/pages/ProjectEditorPage.test.tsx` | Cubierto | Hay evidencia backend y evidencia UI para borrado y navegación posterior |
| REQ-03 | Actualizar solo `Programm` o solo `Grundstück` debe crear una nueva versión conservando la parte no modificada | `backend/src/cimiento/api/routers/projects.py`, `docs/manual-usuario.md` | `test_patch_program_creates_new_version_with_updated_floors`; `test_patch_solar_creates_new_version_with_updated_north_angle` | Cubierto | Este requisito fue reforzado durante el mantenimiento |
| REQ-04 | El proyecto debe reflejar frescura de datos cuando cambian versiones u outputs asociados | `backend/src/cimiento/persistence/repository.py` | `test_project_updated_at_changes_when_creating_new_version`; `test_project_updated_at_changes_when_version_or_outputs_change`; aserción de `updated_at` en `test_patch_program_creates_new_version_with_updated_floors` | Cubierto | Requisito de consistencia interna crítico para UI y listados |
| REQ-05 | La generación del anteproyecto debe arrancar como job asíncrono y publicar eventos de progreso consultables | `backend/src/cimiento/api/routers/generation.py`, `docs/manual-usuario.md` | `test_generation_job_websocket_and_downloads` | Parcial | Backend cubierto; falta prueba específica del `ProjectGenerationPanel` en frontend |
| REQ-06 | Una generación exitosa debe producir outputs descargables en IFC, DXF, XLSX y SVG | `README.md`, `backend/src/cimiento/api/routers/generation.py` | `test_generation_job_websocket_and_downloads` | Cubierto | La descarga backend está validada |
| REQ-07 | La pestaña `Modell` debe depender de la existencia de IFC y permitir al usuario acceder al visor | `docs/manual-usuario.md`, `frontend/src/pages/ProjectEditorPage.tsx` | `frontend/src/pages/ProjectEditorPage.test.tsx` | Parcial | Se prueba el gating de la pestaña, pero no la interacción de `IfcModelWorkspace` |
| REQ-08 | El asistente conversacional debe ser contextual al proyecto activo | `docs/manual-usuario.md`, `frontend/src/features/chat/ChatPanel.tsx` | `frontend/src/features/chat/ChatPanel.test.tsx` | Parcial | El aislamiento por proyecto y el `thread_id` estable están cubiertos; falta prueba backend del stream de chat |
| REQ-09 | El análisis visual debe aceptar imágenes soportadas, rechazar formatos no válidos y marcar siempre revisión humana | `README.md`, `docs/manual-usuario.md`, `backend/src/cimiento/api/routers/vision.py` | `backend/tests/unit/test_vision_router.py`; `frontend/src/api/vision.test.ts` | Parcial | API y contrato frontend cubiertos; falta prueba UI del diálogo de análisis |
| REQ-10 | La galería de renders debe permitir lanzar un render, seguir su progreso, listar resultados y descargar imágenes | `README.md`, `docs/manual-usuario.md`, `backend/src/cimiento/api/routers/renders.py`, `frontend/src/pages/ProjectRendersPage.tsx` | `test_render_job_gallery_and_download_by_id`; `frontend/src/pages/ProjectRendersPage.test.tsx` | Parcial | Cobertura fuerte del flujo lógico, pero con render mockeado; falta smoke real con Blender |
| REQ-11 | La difusión debe permitir subir imagen, lanzar job, manejar estados `processing/done/error` y refrescar galería | `README.md`, `backend/src/cimiento/api/routers/diffusion.py`, `frontend/src/features/diffusion/DiffusionComposerDialog.tsx` | `frontend/src/features/diffusion/DiffusionComposerDialog.test.tsx` | Parcial | No se ha localizado prueba backend específica del endpoint de difusión |
| REQ-12 | La vista de renders debe permitir refinar tanto renders como imágenes de difusión usando la imagen origen | `frontend/src/pages/ProjectRendersPage.tsx` | `frontend/src/pages/ProjectRendersPage.test.tsx` | Cubierto | El flujo de apertura del diálogo con `initialImageUrl` queda cubierto |
| REQ-13 | La aplicación debe resolver las rutas principales (`/`, `/projekte`, `/projekte/neu`, `/projekte/:id`, `/projekte/:id/renders`) y redirigir rutas desconocidas | `frontend/src/App.tsx` | `frontend/src/App.test.tsx` | Cubierto | También se valida `document.documentElement.lang = "de"` |

## Requisitos que hoy no deben tratarse como bug

- El historial del chat no persiste entre páginas: está documentado como limitación actual en `docs/manual-usuario.md` y en `frontend/src/features/chat/ChatPanel.tsx`.
- La pestaña de modelo depende de que exista IFC: es comportamiento esperado, no defecto.
- La visión siempre requiere revisión humana: si el sistema devuelve `review_required`, está cumpliendo el contrato.
- Render y difusión son dependientes del hardware y no garantizan tiempos bajos en todos los hosts.

## Resultado resumido

- Cubiertos: 6 requisitos.
- Parciales: 7 requisitos.
- Huecos completos identificados en este muestreo: 0 sobre flujos núcleo, pero sí varias brechas de integración.

## Siguientes cierres recomendados

1. Cerrar `REQ-05` con tests de `ProjectGenerationPanel`.
2. Cerrar `REQ-07` con tests del visor IFC real en frontend.
3. Cerrar `REQ-08` con tests backend del WebSocket de chat.
4. Cerrar `REQ-09` con tests de `PlanAnalyzerDialog`.
5. Cerrar `REQ-11` con tests backend del endpoint de difusión.