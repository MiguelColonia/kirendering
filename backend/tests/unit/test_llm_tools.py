"""
Tests de las herramientas del agente copiloto (llm/tools).

Cubren los tres tools sin dependencia de Ollama ni LangGraph:
- solve_distribution: invoca el solver real CP-SAT.
- validate_program_feasibility: análisis geométrico puro (sin solver).
- build_and_export_ifc: pipeline completo builder + IFC sobre tmp.
"""

from pathlib import Path

import pytest

from cimiento.llm.tools import (
    ALL_TOOL_DEFINITIONS,
    TOOL_REGISTRY,
    ExportResult,
    FeasibilityReport,
    IssueLevel,
    SolveResult,
    build_and_export_ifc,
    solve_distribution,
    validate_program_feasibility,
)
from cimiento.schemas import (
    Point2D,
    Polygon2D,
    Program,
    Room,
    RoomType,
    Solar,
    Typology,
    TypologyMix,
)
from cimiento.schemas.solution import SolutionStatus

pytest_plugins = ["tests.fixtures.valid_cases"]


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture
def solar_rectangular() -> Solar:
    return Solar(
        id="solar-test",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=20.0, y=0.0),
                Point2D(x=20.0, y=30.0),
                Point2D(x=0.0, y=30.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )


@pytest.fixture
def typology_t2() -> Typology:
    return Typology(
        id="T2",
        name="Vivienda dos dormitorios",
        min_useful_area=70.0,
        max_useful_area=90.0,
        num_bedrooms=2,
        num_bathrooms=1,
        rooms=[
            Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5),
            Room(type=RoomType.BEDROOM, min_area=10.0, min_short_side=2.5),
            Room(type=RoomType.BATHROOM, min_area=4.0, min_short_side=1.5),
        ],
    )


@pytest.fixture
def program_3_t2(typology_t2: Typology) -> Program:
    return Program(
        project_id="test-proj",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[typology_t2],
        mix=[TypologyMix(typology_id="T2", count=3)],
    )


# ---------------------------------------------------------------------------
# Tests de solve_distribution
# ---------------------------------------------------------------------------


def test_solve_distribution_returns_solve_result(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """solve_distribution devuelve un SolveResult con solution embebida."""
    result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    assert isinstance(result, SolveResult)


def test_solve_distribution_feasible(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """Con solar 20×30 m y 3 T2, el solver debe encontrar solución."""
    result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    assert result.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    assert result.num_units_placed == 3


def test_solve_distribution_metrics_consistent(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """Las métricas del SolveResult deben ser consistentes con la Solution embebida."""
    result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    assert result.num_units_placed == result.solution.metrics.num_units_placed
    assert result.total_area_m2 == result.solution.metrics.total_assigned_area


def test_solve_distribution_infeasible_solar_too_small(typology_t2: Typology) -> None:
    """Solar 5×5 m no puede albergar ninguna unidad T2 de 70 m²."""
    tiny_solar = Solar(
        id="tiny",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=5.0, y=0.0),
                Point2D(x=5.0, y=5.0),
                Point2D(x=0.0, y=5.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=9.0,
    )
    program = Program(
        project_id="test-infeasible",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[typology_t2],
        mix=[TypologyMix(typology_id="T2", count=1)],
    )
    result = solve_distribution(tiny_solar, program, timeout_seconds=5)
    assert result.status == SolutionStatus.INFEASIBLE
    assert result.num_units_placed == 0


# ---------------------------------------------------------------------------
# Tests de validate_program_feasibility
# ---------------------------------------------------------------------------


def test_validate_feasibility_returns_report(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """validate_program_feasibility devuelve un FeasibilityReport."""
    report = validate_program_feasibility(solar_rectangular, program_3_t2)
    assert isinstance(report, FeasibilityReport)


def test_validate_feasibility_ok_case(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """Solar 20×30 m con 3 T2 en 1 planta es viable."""
    report = validate_program_feasibility(solar_rectangular, program_3_t2)
    assert report.is_feasible is True
    assert not any(i.level == IssueLevel.ERROR for i in report.issues)


def test_validate_feasibility_height_exceeded(
    solar_rectangular: Solar, typology_t2: Typology
) -> None:
    """Programa con más plantas de las permitidas por altura máxima produce ERROR."""
    program_too_tall = Program(
        project_id="test-tall",
        num_floors=10,
        floor_height_m=3.0,
        typologies=[typology_t2],
        mix=[TypologyMix(typology_id="T2", count=2)],
    )
    # solar_rectangular tiene max_buildable_height_m=9.0 → permite 3 plantas a 3 m
    report = validate_program_feasibility(solar_rectangular, program_too_tall)
    assert report.is_feasible is False
    codes = [i.code for i in report.issues]
    assert "HEIGHT_EXCEEDED" in codes


def test_validate_feasibility_area_infeasible(
    solar_rectangular: Solar, typology_t2: Typology
) -> None:
    """Programa que requiere mucho más área que la edificable produce ERROR."""
    program_overloaded = Program(
        project_id="test-overloaded",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[typology_t2],
        mix=[TypologyMix(typology_id="T2", count=20)],
    )
    # Solar 600 m² × 1 planta × 0.70 = 420 m² edificable; 20 × 70 = 1400 m² requeridos
    report = validate_program_feasibility(solar_rectangular, program_overloaded)
    assert report.is_feasible is False
    codes = [i.code for i in report.issues]
    assert "AREA_INFEASIBLE" in codes


def test_validate_feasibility_empty_program(solar_rectangular: Solar) -> None:
    """Programa sin unidades en el mix produce INFO, no ERROR."""
    typology = Typology(
        id="T1",
        name="T1",
        min_useful_area=50.0,
        max_useful_area=70.0,
        num_bedrooms=1,
        num_bathrooms=1,
        rooms=[Room(type=RoomType.LIVING, min_area=15.0, min_short_side=3.0)],
    )
    program_empty = Program(
        project_id="test-empty",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[typology],
        mix=[],
    )
    report = validate_program_feasibility(solar_rectangular, program_empty)
    assert report.is_feasible is True
    codes = [i.code for i in report.issues]
    assert "EMPTY_PROGRAM" in codes


def test_validate_feasibility_solar_area_populated(
    solar_rectangular: Solar, program_3_t2: Program
) -> None:
    """El informe incluye las métricas de área correctas."""
    report = validate_program_feasibility(solar_rectangular, program_3_t2)
    assert report.solar_area_m2 == pytest.approx(600.0, abs=1.0)
    assert report.required_area_m2 == pytest.approx(210.0, abs=1.0)  # 3 × 70


def test_validate_feasibility_errors_before_warnings(
    solar_rectangular: Solar, typology_t2: Typology
) -> None:
    """Los ERRORs aparecen antes que los WARNINGs en la lista de issues."""
    program_overloaded = Program(
        project_id="test-order",
        num_floors=10,
        floor_height_m=3.0,
        typologies=[typology_t2],
        mix=[TypologyMix(typology_id="T2", count=20)],
    )
    report = validate_program_feasibility(solar_rectangular, program_overloaded)
    levels = [i.level for i in report.issues]
    # Una vez aparece un WARNING/INFO no puede seguir un ERROR
    last_error_idx = max((i for i, lv in enumerate(levels) if lv == IssueLevel.ERROR), default=-1)
    first_warning_idx = next((i for i, lv in enumerate(levels) if lv != IssueLevel.ERROR), len(levels))
    assert last_error_idx < first_warning_idx


# ---------------------------------------------------------------------------
# Tests de build_and_export_ifc
# ---------------------------------------------------------------------------


def test_build_and_export_ifc_produces_file(
    tmp_path: Path,
    solar_rectangular: Solar,
    program_3_t2: Program,
) -> None:
    """build_and_export_ifc crea un archivo IFC válido en el directorio indicado."""
    solve_result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    assert solve_result.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)

    export_result = build_and_export_ifc(
        solar=solar_rectangular,
        program=program_3_t2,
        solution=solve_result.solution,
        output_dir=tmp_path,
        project_id="test-proj",
    )
    assert isinstance(export_result, ExportResult)
    assert Path(export_result.output_path).exists()


def test_build_and_export_ifc_is_valid(
    tmp_path: Path,
    solar_rectangular: Solar,
    program_3_t2: Program,
) -> None:
    """El IFC generado pasa la validación de ifcopenshell."""
    solve_result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    export_result = build_and_export_ifc(
        solar=solar_rectangular,
        program=program_3_t2,
        solution=solve_result.solution,
        output_dir=tmp_path,
        project_id="test-proj",
    )
    assert export_result.is_valid_ifc is True


def test_build_and_export_ifc_counts_spaces(
    tmp_path: Path,
    solar_rectangular: Solar,
    program_3_t2: Program,
) -> None:
    """El número de espacios exportados coincide con las unidades colocadas."""
    solve_result = solve_distribution(solar_rectangular, program_3_t2, timeout_seconds=30)
    export_result = build_and_export_ifc(
        solar=solar_rectangular,
        program=program_3_t2,
        solution=solve_result.solution,
        output_dir=tmp_path,
        project_id="test-proj",
    )
    assert export_result.num_spaces == solve_result.num_units_placed


# ---------------------------------------------------------------------------
# Tests del registro y definiciones
# ---------------------------------------------------------------------------


def test_tool_registry_contains_all_tools() -> None:
    """TOOL_REGISTRY contiene las tres herramientas esperadas."""
    assert "solve_distribution" in TOOL_REGISTRY
    assert "validate_program_feasibility" in TOOL_REGISTRY
    assert "build_and_export_ifc" in TOOL_REGISTRY


def test_all_tool_definitions_format() -> None:
    """Cada definición Ollama tiene la estructura mínima requerida."""
    assert len(ALL_TOOL_DEFINITIONS) == 3
    for tool_def in ALL_TOOL_DEFINITIONS:
        assert tool_def["type"] == "function"
        fn = tool_def["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert isinstance(fn["description"], str) and len(fn["description"]) > 10
