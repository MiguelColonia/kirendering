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

### 🔄 Cambiado
- Sin cambios.

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
