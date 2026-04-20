# Changelog

Registro de todos los cambios relevantes del proyecto ordenados
por versión. Sigue el estándar Keep a Changelog y Semantic Versioning.

## Versionado
- MAJOR (1.0.0): cambios incompatibles con versiones anteriores
- MINOR (0.1.0): nueva funcionalidad compatible con lo anterior
- PATCH (0.0.1): corrección de bugs compatible con lo anterior

---

## [Unreleased]
Cambios que están en desarrollo y aún no tienen versión asignada.

### ➕ Añadido
- Tests unitarios del endpoint `/health` en `backend/tests/unit/test_api_main.py`.
- Documentación de alto nivel del proyecto en `CHANGELOG.md`, `DECISIONS.md` y `ROADMAP.md`.
- Hoja de ruta actualizada con estado de Fase 3 y tareas transversales de calidad/documentación.
- Documento de cierre de Fase 4 en `docs/progress/fase-04.md`.
- ADR-0007 para fijar el stack frontend y el criterio de una SPA local con visor IFC.
- Screenshots de la UI para el `README.md`.
- Dockerfiles de backend y frontend, más despliegue web completo en `infra/docker/docker-compose.yml`.

### 🔄 Cambiado
- Redacción de `ROADMAP.md` para mejorar legibilidad, consistencia de fases y estado actual del proyecto.
- `README.md`, `CLAUDE.md` y `Claude.md` para reflejar que Fase 4 está cerrada y que el siguiente foco es Fase 5.
- Resolución de base URL del frontend para usar el mismo origen por defecto y funcionar detrás del proxy web del despliegue local.

### 🗑️ Eliminado
- Sin cambios.

### 🐛 Corregido
- Sin cambios.

### 🔒 Seguridad
- Auditoría de seguridad inicial documentada con foco en configuración, CORS, inyección y hardening HTTP.

### ⚠️ Deprecado
- Sin cambios.

---

## [0.1.0] — 2026-04-20
### ➕ Añadido
- Estructura inicial del proyecto.
- Solver CP-SAT base para distribución residencial.
- Schemas Pydantic v2 para geometría, programa y solución.
- Exportación BIM inicial a IFC4, DXF y XLSX.
