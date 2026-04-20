"""
Tests de contrato para el módulo geometry.builder.

Verifican que build_building_from_solution produce la jerarquía BIM correcta
a partir de una Solution real del solver (no mocks).
"""

import pytest

from cimiento.geometry import build_building_from_solution
from cimiento.schemas import (
    Building,
    OpeningType,
    Program,
    SlabType,
    Solar,
    Typology,
    TypologyMix,
    WallType,
)

pytest_plugins = ["tests.fixtures.valid_cases"]


# ---------------------------------------------------------------------------
# Fixture: programa de 5 unidades T2 + solar 20×30 m
# ---------------------------------------------------------------------------


@pytest.fixture
def program_5_t2(sample_typology_t2: Typology) -> Program:
    return Program(
        project_id="builder-test",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=5)],
    )


@pytest.fixture
def building_5_t2(sample_solar_rectangular: Solar, program_5_t2: Program) -> Building:
    from cimiento.solver import solve

    solution = solve(sample_solar_rectangular, program_5_t2)
    return build_building_from_solution(sample_solar_rectangular, program_5_t2, solution)


@pytest.fixture
def building_3_floors(sample_typology_t2: Typology) -> Building:
    from cimiento.schemas import Point2D, Polygon2D
    from cimiento.solver import solve

    solar = Solar(
        id="solar-builder-40x40",
        contour=Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=40.0, y=0.0),
                Point2D(x=40.0, y=40.0),
                Point2D(x=0.0, y=40.0),
            ]
        ),
        north_angle_deg=0.0,
        max_buildable_height_m=15.0,
    )
    program = Program(
        project_id="builder-multifloor",
        num_floors=3,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=12)],
    )
    solution = solve(solar, program)
    return build_building_from_solution(solar, program, solution)


@pytest.fixture
def building_with_parking(sample_typology_t2: Typology) -> Building:
    from cimiento.schemas import Point2D, Polygon2D
    from cimiento.solver import solve, solve_parking

    solar = Solar(
        id="solar-builder-parking-60x60",
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
        project_id="builder-parking",
        num_floors=5,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=20)],
    )
    solution = solve(solar, program)
    parking = solve_parking(solar, solution, floor_height_m=program.floor_height_m)
    return build_building_from_solution(solar, program, solution, parking_solution=parking)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuilderBasic:
    def test_building_has_five_spaces(self, building_5_t2: Building) -> None:
        """Cinco unidades T2 → cinco Spaces en el Building resultante."""
        total = sum(len(s.spaces) for s in building_5_t2.storeys)
        assert total == 5

    def test_each_space_has_at_least_one_door(self, building_5_t2: Building) -> None:
        """Cada Space debe tener al menos una puerta (Opening DOOR en un muro adyacente)."""
        for storey in building_5_t2.storeys:
            doors = [o for o in storey.openings if o.opening_type == OpeningType.DOOR]
            assert len(doors) >= len(storey.spaces), (
                f"Storey {storey.id} tiene {len(storey.spaces)} spaces "
                f"pero solo {len(doors)} puertas"
            )

    def test_exterior_wall_count_matches_solar_contour(
        self,
        building_5_t2: Building,
        sample_solar_rectangular: Solar,
    ) -> None:
        """Los muros exteriores deben coincidir en número con los lados del solar."""
        expected = len(sample_solar_rectangular.contour.points)
        for storey in building_5_t2.storeys:
            ext_walls = [w for w in storey.walls if w.wall_type == WallType.EXTERIOR]
            assert len(ext_walls) == expected, (
                f"Storey {storey.id}: {len(ext_walls)} muros exteriores, se esperaban {expected}"
            )

    def test_ground_floor_slab_covers_solar_contour(
        self,
        building_5_t2: Building,
        sample_solar_rectangular: Solar,
    ) -> None:
        """El forjado de suelo de planta baja debe usar el contorno del solar."""
        ground = next(s for s in building_5_t2.storeys if s.level == 0)
        floor_slabs = [sl for sl in ground.slabs if sl.slab_type == SlabType.GROUND_FLOOR]
        assert len(floor_slabs) >= 1, "No hay forjado de suelo en planta baja"

        slab = floor_slabs[0]
        solar_pts = sample_solar_rectangular.contour.points
        assert len(slab.contour.points) == len(solar_pts)
        for sp, solp in zip(slab.contour.points, solar_pts):
            assert sp.x == pytest.approx(solp.x)
            assert sp.y == pytest.approx(solp.y)

    def test_builder_creates_storey_per_program_floor(self, building_3_floors: Building) -> None:
        """El builder debe crear una Storey por cada planta del programa."""
        levels = sorted(s.level for s in building_3_floors.storeys)
        assert levels == [0, 1, 2]

    def test_builder_propagates_communication_cores(self, building_3_floors: Building) -> None:
        """Los núcleos calculados por el solver deben llegar al Building final."""
        assert len(building_3_floors.communication_cores) >= 1
        for core in building_3_floors.communication_cores:
            assert core.serves_floors == [0, 1, 2]

    def test_builder_includes_parking_storey(self, building_with_parking: Building) -> None:
        """Si existe layout de parking, el building final debe incluir la planta -1."""
        parking_storeys = [s for s in building_with_parking.storeys if s.level == -1]
        assert len(parking_storeys) == 1
        parking_storey = parking_storeys[0]
        assert len(parking_storey.spaces) > 0
        assert hasattr(parking_storey, "lanes")
