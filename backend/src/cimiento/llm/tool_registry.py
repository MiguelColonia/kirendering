"""
Registro central de herramientas del agente copiloto de Cimiento.

Expone al grafo LangGraph:
- ``SYNC_TOOLS``: herramientas síncronas (solver, métricas, normativa, sugerencias).
- ``ASYNC_TOOLS``: herramientas asíncronas que requieren llamadas al LLM (descripción).
- ``ALL_TOOL_DEFINITIONS``: lista de definiciones en formato Ollama lista para
  pasarse como ``tools=ALL_TOOL_DEFINITIONS`` a ``OllamaClient.chat()``.

Las tools anteriores (solver_tools, validation_tools, bim_tools) siguen disponibles
en el paquete ``llm.tools`` para uso directo; este registro representa el contrato
público entre el grafo y las capacidades del agente.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cimiento.llm.tools.bim_tools import BUILD_AND_EXPORT_TOOL, build_and_export_ifc
from cimiento.llm.tools.calculate_metrics import CALCULATE_METRICS_TOOL, calculate_metrics
from cimiento.llm.tools.describe_solution import DESCRIBE_SOLUTION_TOOL, describe_solution
from cimiento.llm.tools.query_regulation import QUERY_REGULATION_TOOL, query_regulation
from cimiento.llm.tools.solve_layout import SOLVE_LAYOUT_TOOL, solve_layout
from cimiento.llm.tools.suggest_typology_adjustments import (
    SUGGEST_ADJUSTMENTS_TOOL,
    suggest_typology_adjustments,
)
from cimiento.llm.tools.validation_tools import (
    VALIDATE_FEASIBILITY_TOOL,
    validate_program_feasibility,
)

# ---------------------------------------------------------------------------
# Herramientas síncronas: el grafo puede llamarlas directamente
# ---------------------------------------------------------------------------

SYNC_TOOLS: dict[str, Callable[..., Any]] = {
    "validate_program_feasibility": validate_program_feasibility,
    "solve_layout": solve_layout,
    "calculate_metrics": calculate_metrics,
    "query_regulation": query_regulation,
    "suggest_typology_adjustments": suggest_typology_adjustments,
    "build_and_export_ifc": build_and_export_ifc,
}

# ---------------------------------------------------------------------------
# Herramientas asíncronas: el grafo debe ejecutarlas con await
# ---------------------------------------------------------------------------

ASYNC_TOOLS: dict[str, Callable[..., Any]] = {
    "describe_solution": describe_solution,
}

# ---------------------------------------------------------------------------
# Registro unificado para despacho en el ejecutor de tools del grafo
# ---------------------------------------------------------------------------

ALL_REGISTERED_TOOLS: dict[str, Callable[..., Any]] = {**SYNC_TOOLS, **ASYNC_TOOLS}

# ---------------------------------------------------------------------------
# Definiciones en formato Ollama (para OllamaClient.chat(tools=...))
# Ordenadas de menor a mayor coste computacional / latencia
# ---------------------------------------------------------------------------

ALL_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    VALIDATE_FEASIBILITY_TOOL,
    QUERY_REGULATION_TOOL,
    SOLVE_LAYOUT_TOOL,
    CALCULATE_METRICS_TOOL,
    SUGGEST_ADJUSTMENTS_TOOL,
    BUILD_AND_EXPORT_TOOL,
    DESCRIBE_SOLUTION_TOOL,
]

__all__ = [
    "SYNC_TOOLS",
    "ASYNC_TOOLS",
    "ALL_REGISTERED_TOOLS",
    "ALL_TOOL_DEFINITIONS",
]
