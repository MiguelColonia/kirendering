"""Tests del registro central de herramientas (tool_registry.py)."""

from cimiento.llm.tool_registry import (
    ALL_REGISTERED_TOOLS,
    ALL_TOOL_DEFINITIONS,
    ASYNC_TOOLS,
    SYNC_TOOLS,
)


def test_sync_tools_are_callable() -> None:
    for name, fn in SYNC_TOOLS.items():
        assert callable(fn), f"SYNC_TOOLS['{name}'] no es callable"


def test_async_tools_are_callable() -> None:
    import asyncio

    for name, fn in ASYNC_TOOLS.items():
        assert callable(fn), f"ASYNC_TOOLS['{name}'] no es callable"
        assert asyncio.iscoroutinefunction(fn), f"ASYNC_TOOLS['{name}'] no es coroutine"


def test_all_registered_tools_union() -> None:
    assert set(ALL_REGISTERED_TOOLS.keys()) == set(SYNC_TOOLS.keys()) | set(ASYNC_TOOLS.keys())


def test_tool_definitions_count() -> None:
    assert len(ALL_TOOL_DEFINITIONS) == 7


def test_tool_definitions_ollama_format() -> None:
    for defn in ALL_TOOL_DEFINITIONS:
        assert defn["type"] == "function"
        fn = defn["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert isinstance(fn["description"], str) and len(fn["description"]) > 10
        assert fn["parameters"]["type"] == "object"


def test_expected_tool_names_present() -> None:
    names = {d["function"]["name"] for d in ALL_TOOL_DEFINITIONS}
    expected = {
        "validate_program_feasibility",
        "solve_layout",
        "query_regulation",
        "calculate_metrics",
        "suggest_typology_adjustments",
        "build_and_export_ifc",
        "describe_solution",
    }
    assert expected == names
