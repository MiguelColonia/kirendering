# Fase 1 — Solver aislado ✓

## Qué se logró

### Schemas implementados

Capa de contratos Pydantic v2 en `backend/src/cimiento/schemas/`:

| Archivo | Clases |
|---|---|
| `geometry_primitives.py` | `Point2D`, `Polygon2D`, `Rectangle` |
| `typology.py` | `RoomType`, `Room`, `Typology` |
| `solar.py` | `Solar` |
| `program.py` | `TypologyMix`, `Program` |
| `solution.py` | `SolutionStatus`, `UnitPlacement`, `SolutionMetrics`, `Solution` |

Todos los campos llevan `Field(description=...)` en español. Validadores activos:
`Point2D` rechaza NaN/Inf; `Polygon2D` rechaza polígonos colineales; `Typology` exige al menos
un LIVING y `min_useful_area < max_useful_area`; `Program` valida que el mix solo referencie
tipologías definidas.

### Solver

Módulo `backend/src/cimiento/solver/engine.py`. Función pública:

```
solve(solar, program, timeout_seconds=60) -> Solution
```

Formulación: discretización en rejilla de 0,5 m; forma canónica fija por tipología
(ancho 7 m, alto ajustado a `min_useful_area`); variables `x_i`, `y_i` de posición por unidad;
restricción `AddNoOverlap2D` sobre `IntervalVar`; objetivo de maximizar área total asignada;
timeout vía `solver.parameters.max_time_in_seconds`.

### Tests

- `tests/unit/test_schemas.py` — 43 tests de contrato (validadores, propiedades calculadas).
- `tests/unit/test_solver_basic.py` — 5 tests TDD del solver (FEASIBLE, INFEASIBLE, área mínima, timeout, programa vacío).
- `tests/fixtures/valid_cases.py` — fixtures `sample_typology_t2`, `sample_solar_rectangular`, `sample_program_10_t2`.

Total: **48 tests, 48 passed**.

## Limitaciones conocidas

1. **Solo solares rectangulares.** El solver usa `contour.bounding_box` como espacio
   disponible; ignora vértices no axiales. Polígonos generales pendientes para Fase 3.
2. **Una sola planta.** El modelo CP-SAT solo distribuye en `floor=0`. Múltiples plantas
   requieren replicar el modelo por planta o añadir una variable de planta.
3. **Sin núcleos de comunicación.** No se reserva espacio para escaleras, ascensores ni
   pasillos comunes. Toda la superficie solar se trata como edificable.
4. **Sin aparcamiento.** No hay tipología ni restricción de plazas de parking.
5. **Dimensiones de unidad fijas.** Cada tipología tiene una forma canónica única (7 m × h m).
   Las dimensiones variables con `AddMultiplicationEquality` quedan para Fase 2.

## Cómo ejecutar el caso de ejemplo

```bash
cd backend

# Ejecutar todos los tests
uv run pytest tests/unit/ -v

# Visualizar la solución en SVG
uv run python scripts/visualize_solution.py ../data/solares_ejemplo/rectangular_simple.yaml
# → genera data/outputs/rectangular_simple.svg
```

## Qué viene en Fase 2

- Capa `geometry/`: operaciones sobre polígonos reales (intersección, área, offset de fachada).
- Soporte de solares no rectangulares en el solver (máscara de celdas prohibidas).
- Exportación BIM básica a IFC con IfcOpenShell (contorno del solar + footprints de unidades).
- Tests de integración solver → geometría.
