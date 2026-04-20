# ADR 0001: Usar OR-Tools como solver, no el LLM

## Contexto

Se consideró que agentes LLM en LangGraph resolvieran el problema de distribución.

## Decisión

Usar OR-Tools CP-SAT como solver. El LLM solo invoca el solver.

## Razones

- Los LLMs alucinan números y no garantizan factibilidad.
- La normativa es dura: no admite errores silenciosos.
- OR-Tools es determinista, auditable y escala a problemas reales.
