"""
Tests de integración para el exportador IFC4.

Ejecutan el pipeline completo: solver → builder → export_to_ifc.
No son tests unitarios: dependen del filesystem y del solver real.
"""

from pathlib import Path

import ifcopenshell
import pytest

from cimiento.bim import ValidationResult, export_to_ifc, validate_ifc
from cimiento.geometry import build_building_from_solution
from cimiento.schemas import Program, Solar, Typology, TypologyMix

pytest_plugins = ["tests.fixtures.valid_cases"]


@pytest.fixture
def building_for_ifc(sample_solar_rectangular: Solar, sample_typology_t2: Typology):
    from cimiento.solver import solve

    program = Program(
        project_id="ifc-test",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )
    solution = solve(sample_solar_rectangular, program)
    return build_building_from_solution(sample_solar_rectangular, program, solution)


@pytest.fixture
def exported_ifc_path(building_for_ifc, tmp_path: Path) -> Path:
    path = tmp_path / "test_export.ifc"
    export_to_ifc(building_for_ifc, path)
    return path


@pytest.fixture
def parking_exported_ifc_path(sample_typology_t2: Typology, tmp_path: Path) -> Path:
    from cimiento.schemas import Point2D, Polygon2D
    from cimiento.solver import solve, solve_parking

    solar = Solar(
        id="solar-ifc-parking-60x60",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=60.0, y=0.0),
                Point2D(x=60.0, y=60.0),
                Point2D(x=0.0, y=60.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=18.0,
    )
    program = Program(
        project_id="ifc-parking-test",
        num_floors=5,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=20)],
    )
    residential = solve(solar, program)
    parking = solve_parking(solar, residential, floor_height_m=program.floor_height_m)
    building = build_building_from_solution(solar, program, residential, parking_solution=parking)
    path = tmp_path / "test_export_parking.ifc"
    export_to_ifc(building, path)
    return path


class TestIfcExport:
    def test_ifc_file_is_created(self, exported_ifc_path: Path) -> None:
        """El archivo .ifc debe existir y tener contenido."""
        assert exported_ifc_path.exists()
        assert exported_ifc_path.stat().st_size > 0

    def test_ifc_file_starts_with_step_header(self, exported_ifc_path: Path) -> None:
        """Un archivo IFC válido empieza por 'ISO-10303-21' (formato STEP)."""
        header = exported_ifc_path.read_text(encoding="utf-8")[:20]
        assert header.startswith("ISO-10303-21")

    def test_validate_ifc_returns_valid(self, exported_ifc_path: Path) -> None:
        """validate_ifc debe marcar el archivo como válido."""
        result: ValidationResult = validate_ifc(exported_ifc_path)
        assert result.valid, f"IFC inválido. Avisos: {result.warnings}"

    def test_ifc_contains_required_entities(self, exported_ifc_path: Path) -> None:
        """El IFC debe contener al menos 1 edificio, 1 planta, 5 espacios y 4 muros."""
        result = validate_ifc(exported_ifc_path)
        assert result.num_buildings >= 1, "Falta IfcBuilding"
        assert result.num_storeys >= 1, "Falta IfcBuildingStorey"
        assert result.num_spaces >= 5, f"Se esperaban ≥5 IfcSpace, hay {result.num_spaces}"
        assert result.num_walls >= 4, f"Se esperaban ≥4 IfcWall, hay {result.num_walls}"

    def test_ifc_contains_doors(self, exported_ifc_path: Path) -> None:
        """Debe haber al menos una IfcDoor (una por cada unidad)."""
        result = validate_ifc(exported_ifc_path)
        assert result.num_doors >= 5, (
            f"Se esperaban ≥5 IfcDoor (una por unidad), hay {result.num_doors}"
        )

    def test_ifc_contains_vertical_core_elements(self, exported_ifc_path: Path) -> None:
        """La exportación debe incluir escalera y elemento de transporte vertical."""
        result = validate_ifc(exported_ifc_path)
        assert result.num_stairs >= 1, "Se esperaba al menos un IfcStair"
        assert result.num_transport_elements >= 1, (
            "Se esperaba al menos un IfcTransportElement para el ascensor"
        )

    def test_validate_nonexistent_file_returns_invalid(self, tmp_path: Path) -> None:
        """validate_ifc en ruta inexistente debe devolver valid=False."""
        result = validate_ifc(tmp_path / "no_existe.ifc")
        assert not result.valid
        assert result.warnings

    def test_ifc_contains_parking_spaces(self, parking_exported_ifc_path: Path) -> None:
        """Las plazas de parking deben exportarse como IfcSpace con PredefinedType=PARKING."""
        model = ifcopenshell.open(str(parking_exported_ifc_path))
        parking_spaces = [
            s for s in model.by_type("IfcSpace") if getattr(s, "PredefinedType", None) == "PARKING"
        ]
        assert parking_spaces, "No se encontraron IfcSpace con PredefinedType=PARKING"

    def test_ifc_contains_parking_storey(self, parking_exported_ifc_path: Path) -> None:
        """El caso con aparcamiento debe exportar al menos una planta adicional bajo rasante."""
        result = validate_ifc(parking_exported_ifc_path)
        assert result.num_storeys >= 6, (
            f"Se esperaban al menos 6 plantas IFC, hay {result.num_storeys}"
        )

    def test_ifc_exports_core_elements_per_floor(
        self,
        sample_typology_t2: Typology,
        tmp_path: Path,
    ) -> None:
        """
        En un edificio multiplanta, el exportador debe crear un IfcStair y un
        IfcTransportElement por cada planta servida por cada núcleo.
        """
        from cimiento.schemas import Point2D, Polygon2D
        from cimiento.solver import solve

        solar = Solar(
            id="solar-ifc-3f-40x40",
            contour=Polygon2D(
                points=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=40.0, y=0.0),
                    Point2D(x=40.0, y=40.0),
                    Point2D(x=0.0, y=40.0),
                ]
            ),
            north_angle_deg=0.0,
            max_buildable_height_m=12.0,
        )
        program = Program(
            project_id="ifc-multifloor-cores",
            num_floors=3,
            floor_height_m=3.0,
            typologies=[sample_typology_t2],
            mix=[TypologyMix(typology_id="T2", count=12)],
        )

        solution = solve(solar, program)
        assert solution.communication_cores, "El solver debe generar al menos un núcleo"

        building = build_building_from_solution(solar, program, solution)
        path = tmp_path / "multifloor_cores.ifc"
        export_to_ifc(building, path)
        result = validate_ifc(path)

        num_cores = len(solution.communication_cores)
        num_floors = program.num_floors
        expected = num_cores * num_floors

        assert result.num_stairs == expected, (
            f"Se esperaban {expected} IfcStair ({num_cores} núcleo(s) × {num_floors} plantas), "
            f"hay {result.num_stairs}"
        )
        if solution.communication_cores[0].has_elevator:
            assert result.num_transport_elements == expected, (
                f"Se esperaban {expected} IfcTransportElement, hay {result.num_transport_elements}"
            )
