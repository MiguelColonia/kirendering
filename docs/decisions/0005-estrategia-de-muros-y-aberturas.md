# ADR 0005 — Estrategia de modelado de muros y aperturas

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Contexto:** Fase 2, diseño del schema arquitectónico.

---

## Contexto

El modelo arquitectónico necesita representar muros con huecos (puertas y ventanas).
Existen dos enfoques principales:

1. **Polígono con hueco**: el muro es un polígono con una cavidad recortada.
2. **Segmento + posición relativa**: el muro es un segmento de eje central y el
   hueco es una posición normalizada a lo largo de ese segmento.

---

## Decisión 1: Muros como segmentos extruidos (Wall)

Un `Wall` se modela como un segmento 2D (start_point → end_point) con espesor y altura,
NO como un polígono con cavidades.

**Por qué:**

1. **Compatibilidad con IFC**: IFC define `IfcWallStandardCase` exactamente así —
   eje central, espesor, altura de extrusión. Un polígono con hueco requeriría
   `IfcWall` genérico con geometría booleana, perdiendo la semántica estándar.

2. **Interoperabilidad con Revit / ArchiCAD**: ambas plataformas infieren el espesor,
   las uniones de esquina y los acabados automáticamente desde `IfcWallStandardCase`.
   Con un polígono genérico, el arquitecto tendría que re-parametrizar todo.

3. **Simplicidad del solver**: el solver CP-SAT trabaja con rectángulos (bboxes). La
   traslación bbox → segmento es trivial (4 segmentos por bbox); la traslación
   bbox → polígono con huecos requeriría geometría computacional adicional.

4. **Extensibilidad**: pasar de segmento a curva NURBS (muros curvos) en Fase 3
   solo requiere cambiar la geometría de extrusión, no el schema completo.

---

## Decisión 2: Posición relativa [0,1] para aperturas (Opening)

El campo `position_along_wall_m` almacena una posición normalizada entre 0.0
(extremo start_point) y 1.0 (extremo end_point), NO coordenadas absolutas.

**Por qué:**

1. **Invarianza ante modificaciones del muro**: si el muro se desplaza, alarga
   o acorta, la puerta mantiene su posición relativa semánticamente correcta sin
   recalcular nada. Con coordenadas absolutas, cada modificación del muro invalidaría
   las posiciones de todas sus aperturas.

2. **Correspondencia con IFC**: `IfcRelVoidsElement` + `IfcOpeningElement` usa el
   sistema de referencia local del muro, que es exactamente lo que codifica la
   posición relativa. La conversión es `abs_pos = pos_relativa × longitud_muro`.

3. **Validación simple**: la restricción `ge=0.0, le=1.0` es unívoca e independiente
   de la longitud del muro. Con coordenadas absolutas, la validación cruzada
   (la posición debe estar dentro del muro) requeriría un model_validator más complejo.

**Precio:**

Las coordenadas absolutas de la apertura NO están en el schema; hay que calcularlas
en la capa BIM (`ifc_exporter.py`) usando `start_point + pos × (end_point - start_point)`.
Esto es intencional: el schema es el contrato abstracto, la geometría concreta se
deriva en la capa de exportación.

---

## Consecuencias

- `Wall.start_point`, `Wall.end_point` son los puntos del eje central; el muro
  se extiende `thickness_m/2` a cada lado del eje.
- `Opening.position_along_wall_m` es suficiente para derivar todas las coordenadas
  3D necesarias para IFC, DXF y SVG.
- Los muros curvos (arcos) se añadirán en Fase 3 extendiendo `Wall` con un campo
  opcional `arc_radius_m`; la posición relativa sigue siendo válida (normalizada
  por longitud de arco).
