# ADR 0006 — Estrategia para solares con forma poligonal arbitraria

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Contexto:** Extensión del solver CP-SAT para soportar polígonos no rectangulares.

---

## Contexto

El solver de Fase 1 solo soportaba solares rectangulares: el espacio discretizado era
exactamente el bounding box del contorno, y las restricciones de confinamiento se
expresaban mediante los dominios de las variables (x ∈ [0, W-w], y ∈ [0, H-h]).

Cualquier solar real puede tener forma poligonal arbitraria (L, U, T, en ángulo, etc.).
Se analizaron dos enfoques para extender el solver.

---

## Opciones consideradas

### Enfoque A — Máscara booleana de celdas + posiciones permitidas (elegido)

1. **Precomputar** qué celdas de la rejilla están dentro del polígono del solar usando
   Shapely (`prepared_polygon.covers(unit_rect)`).
2. Para cada tipo de unidad con forma canónica (w × h):
   - Enumerar todas las posiciones de inicio (cx, cy) del bounding box.
   - Guardar solo las que satisfacen `solar_poly.covers(unit_rect)`.
3. **Añadir a CP-SAT**: `AddAllowedAssignments([x_i, y_i], valid_positions)`

**Ventajas:**
- Correcto para cualquier polígono convexo o cóncavo (L, U, etc.).
- El filtrado ocurre en tiempo de precomputación (Python + Shapely), no dentro de CP-SAT.
- `AddAllowedAssignments` es una restricción eficiente en CP-SAT (tabla hash interna).
- Detección rápida de INFEASIBLE si `valid_positions` queda vacío.
- Reutilizable: las posiciones válidas se calculan una vez por forma (w, h), no por unidad.

**Desventajas:**
- La lista `valid_positions` puede ser grande para solares muy grandes
  (ej. 200 × 400 grid → hasta ~80.000 posiciones por tipo). En ese caso se puede
  sustituir por una restricción de celda-inválida más compacta (ver Fase 3).
- Añade una llamada a Shapely en cada invocación del solver.

### Enfoque B — Restricciones sobre las esquinas de la unidad (descartado)

Para cada unidad, añadir restricciones CP-SAT que fuercen cada esquina dentro del polígono:
`point_in_polygon(corner_j) == True`.

**Por qué se descarta:**
- Incorrecto para polígonos cóncavos: 4 esquinas dentro no garantiza que el interior
  de la unidad esté dentro (la unidad podría "cruzar" la concavidad).
- CP-SAT no tiene predicado `point_in_polygon` nativo; implementarlo requiere
  variables booleanas adicionales y linealización, aumentando el tamaño del modelo.
- Solo sería correcto para polígonos convexos, limitando la utilidad.

---

## Decisión

Se elige el **Enfoque A** por correctitud, simplicidad de implementación y rendimiento
adecuado para los tamaños de solar relevantes (≤ 60 × 120 m → ≤ 14.400 celdas).

### Implementación concreta

```
_valid_placements_for_shape(solar_poly, min_x, min_y, W, H, w, h, res)
    → list[tuple[int, int]]
```

Para cada (cx, cy) con cx ∈ [0, W-w], cy ∈ [0, H-h]:
  - Construir `unit_rect = box(min_x + cx*res, min_y + cy*res,
                                min_x + (cx+w)*res, min_y + (cy+h)*res)`
  - Si `solar_poly.covers(unit_rect)` → incluir (cx, cy)

En CP-SAT: `model.AddAllowedAssignments([x_i, y_i], valid_positions_for_type[i])`

El dominio de x_i e y_i se mantiene para que CP-SAT pueda propagar eficientemente.

---

## Consecuencias

- Solares rectangulares siguen funcionando: `solar_poly.covers(unit_rect)` devuelve
  `True` para todas las posiciones dentro del bbox.
- Se puede verificar la solución con `solar_poly.covers(unit_bbox)` en tests.
- Para solares > 60 × 120 m o rejillas más finas (0,25 m), si `valid_positions` es
  muy grande, sustituir por lista de celdas inválidas + `AddForbiddenAssignments`
  (pendiente Fase 3 si se detecta degradación de rendimiento).
- La dependencia de `shapely` ya estaba declarada en `pyproject.toml`; se activa su uso real.
