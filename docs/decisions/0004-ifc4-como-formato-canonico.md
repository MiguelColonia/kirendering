# ADR 0004 — IFC4 como formato BIM canónico

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Contexto:** Fase 2, primera exportación BIM real.

---

## Contexto

El proyecto necesita un formato de intercambio para el modelo arquitectónico que
sea universal, abierto y compatible con las herramientas del sector (Revit, ArchiCAD,
BIMcollab, Solibri, BIM 360). Se eligió el formato en la primera decisión de arquitectura
pero no se documentó formalmente.

---

## Decisión: IFC4 (ISO 16739-1:2018)

Usamos IFC4 como formato BIM canónico del proyecto con la librería IfcOpenShell.

**Por qué IFC4 y no IFC2x3:**

| Criterio | IFC2x3 | IFC4 |
|---|---|---|
| Estándar vigente | No (publicado 2005) | Sí (ISO 2013, revisado 2018) |
| Soporte en tools | Universal | Universal en tools ≥ 2018 |
| IfcWallStandardCase | Disponible | Disponible (compatible) |
| Nuevas entidades (IfcCovering, IfcBuildingSystem) | No | Sí |
| Performance con IfcOpenShell 0.8 | Similar | Similar |
| Certificación buildingSMART | Solo IFC4 Add2 TC1 | Sí |

La única razón para bajar a IFC2x3 sería compatibilidad con software legado de un
cliente concreto (versiones de Revit o ArchiCAD anteriores a 2018). En ese caso, el
punto de cambio es una sola línea: `ifcopenshell.file(schema='IFC4')` → `schema='IFC2X3'`.

**Por qué IfcOpenShell y no la alternativa PyIFC:**

IfcOpenShell es la implementación de referencia de IFC en Python, con soporte oficial
de buildingSMART, bindings C++ compilados (rendimiento), y una API de alto nivel
(`ifcopenshell.api`) que abstrae las relaciones IFC más complejas. PyIFC es más simple
pero no mantiene paridad con IFC4 y carece de la API de geometría.

---

## Consecuencias

- `ifc_exporter.py` depende de `ifcopenshell>=0.8`.
- Los archivos generados son abribles en BlenderBIM, FreeCAD, BIMvision, Solibri.
- DXF y XLSX son formatos de exportación derivados; nunca son la fuente de verdad.
- Si un cliente necesita IFC2x3, se añade un flag `schema: str = "IFC4"` a `export_to_ifc`.
