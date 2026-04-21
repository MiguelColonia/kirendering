"""
Herramientas del agente copiloto de Cimiento.

Cada herramienta expone una función Python tipada con Pydantic y una definición
en formato Ollama para tool-calling. El grafo LangGraph usa TOOL_REGISTRY para
despachar llamadas y ALL_TOOL_DEFINITIONS para informar al LLM de las capacidades
disponibles.
"""

from cimiento.llm.tools.bim_tools import (
    BUILD_AND_EXPORT_TOOL,
    ExportResult,
    build_and_export_ifc,
)
from cimiento.llm.tools.solver_tools import (
    SOLVE_DISTRIBUTION_TOOL,
    SolveResult,
    solve_distribution,
)
from cimiento.llm.tools.validation_tools import (
    VALIDATE_FEASIBILITY_TOOL,
    FeasibilityIssue,
    FeasibilityReport,
    IssueLevel,
    validate_program_feasibility,
)

ALL_TOOL_DEFINITIONS = [
    VALIDATE_FEASIBILITY_TOOL,
    SOLVE_DISTRIBUTION_TOOL,
    BUILD_AND_EXPORT_TOOL,
]

TOOL_REGISTRY = {
    "validate_program_feasibility": validate_program_feasibility,
    "solve_distribution": solve_distribution,
    "build_and_export_ifc": build_and_export_ifc,
}

__all__ = [
    # Herramientas
    "validate_program_feasibility",
    "solve_distribution",
    "build_and_export_ifc",
    # Tipos de resultado
    "FeasibilityReport",
    "FeasibilityIssue",
    "IssueLevel",
    "SolveResult",
    "ExportResult",
    # Definiciones Ollama
    "VALIDATE_FEASIBILITY_TOOL",
    "SOLVE_DISTRIBUTION_TOOL",
    "BUILD_AND_EXPORT_TOOL",
    "ALL_TOOL_DEFINITIONS",
    # Registro de despacho
    "TOOL_REGISTRY",
]
