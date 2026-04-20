# ADR 0003 — Formulación CP-SAT inicial del solver de distribución espacial

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Contexto:** Fase 1, solver aislado sin integración BIM ni LLM.

---

## Contexto

El solver debe distribuir N unidades residenciales sobre un solar dado, respetando
restricciones de área por tipología y sin solapamientos. Se necesita una formulación
que sea correcta, implementable en pocas sesiones y extensible hacia polígonos generales.

---

## Decisión 1: discretización en rejilla

Se discretiza el espacio del solar en una rejilla regular con resolución configurable
(por defecto 0,5 m por celda). Las variables de posición `x_i`, `y_i` son enteros que
representan columnas y filas de la rejilla.

**Por qué:**
CP-SAT es un solver de satisfacción de restricciones sobre enteros. Para modelar
posiciones continuas en 2D, la única opción compatible con sus primitivas (`IntervalVar`,
`AddNoOverlap2D`) es trabajar con coordenadas enteras. La rejilla transforma el problema
continuo en discreto a un coste de precisión controlado.

**Precio:**
La pérdida de precisión es proporcional al tamaño de celda. Con 0,5 m, el error máximo
en área de una unidad es `(w+1)·(h+1)·0,25 − w·h·0,25 ≈ 0,25·(w+h+1)` m², que para
unidades de 7×10 m es ≈ 4,25 m² (~6 % de 70 m²). Para Fase 2 puede reducirse a 0,25 m
si el rendimiento lo permite, o usarse una rejilla adaptativa por zona del solar.

---

## Decisión 2: `AddNoOverlap2D` para no solapamiento

Se usa la primitiva `AddNoOverlap2D(x_intervals, y_intervals)` de CP-SAT para garantizar
que ningún par de unidades se solape en planta.

**Por qué frente a alternativas:**

| Alternativa | Problema |
|---|---|
| Variables binarias `overlap_{ij}` | Escala O(N²) en número de variables; poco práctico con N > 30 |
| Restricciones de separación manuales (`x_i + w_i ≤ x_j OR x_j + w_j ≤ x_i OR ...`) | Requiere variables de disyunción adicionales; más difícil de depurar |
| `AddNoOverlap2D` | Una sola restricción global; CP-SAT la propaga eficientemente con algoritmos de scheduling 2D; es la primitiva diseñada exactamente para este caso |

`AddNoOverlap2D` fue introducida en OR-Tools precisamente para problemas de empaquetado
2D y scheduling con recursos. Es la opción canónica para este tipo de problema.

---

## Decisión 3: formas canónicas fijas (Fase 1)

En lugar de variables `w_i`, `h_i` con `AddMultiplicationEquality(area, [w, h])`,
la Fase 1 usa dimensiones fijas calculadas a partir de `min_useful_area` con un ancho
estándar de 7 m.

**Por qué:**
`AddMultiplicationEquality` introduce una restricción no lineal que CP-SAT resuelve
mediante descomposición de intervalos. Esto es correcto pero puede aumentar el tiempo
de resolución varios órdenes de magnitud para N > 15, especialmente si los dominios
de `w` y `h` son amplios. Para validar el pipeline end-to-end en Fase 1, la simplificación
es aceptable. Fase 2 introducirá dimensiones variables con dominios acotados.

---

## Límite de escala estimado

Con la formulación actual (formas fijas, `AddNoOverlap2D`, rejilla 0,5 m):

| Unidades | Solar típico | Tiempo esperado |
|---|---|---|
| ≤ 20 | 40×60 m | < 1 s |
| 20–50 | 60×100 m | 1–30 s |
| > 50 | cualquiera | > 60 s (timeout probable) |

Estas estimaciones son conservadoras. CP-SAT es generalmente más rápido gracias a
su propagador de restricciones, pero la explosión combinatoria del empaquetado 2D
es NP-completo en el caso general. Para más de 50 unidades se recomienda explorar:
descomposición por planta con solares pre-segmentados, o relajar a un modelo de
bin-packing continuo con heurísticas de primera solución.

---

## Consecuencias

- El solver es correcto para ≤ 30–40 unidades en tiempo real.
- La rejilla introduce un error sistemático de ≤ 6 % en área por unidad.
- El código es legible y extensible: Fase 2 solo necesita reemplazar `_canonical_shape_cells`
  por variables CP-SAT con `AddMultiplicationEquality`.
- No se descarta LP/MIP como alternativa si CP-SAT escala mal en Fase 2
  (ver ADR 0001 para la elección inicial de OR-Tools).
