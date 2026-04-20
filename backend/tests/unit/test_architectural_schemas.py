"""
Tests de contrato para los schemas arquitectónicos (architectural.py).

Verifican que los validadores críticos rechazan datos inválidos y que las
propiedades calculadas (net_area_m2) devuelven resultados correctos.
No prueban lógica de la capa BIM ni del solver.
"""

import pytest
from pydantic import ValidationError

from cimiento.schemas import (
    Building,
    CommunicationCore,
    Opening,
    OpeningType,
    ParkingDimensions,
    ParkingLane,
    ParkingSpace,
    ParkingSpaceType,
    ParkingStorey,
    Point2D,
    Polygon2D,
    RampAccess,
    Slab,
    SlabType,
    Space,
    Storey,
    Wall,
    WallType,
)
from cimiento.schemas.typology import RoomType

# ---------------------------------------------------------------------------
# Helpers de construcción reutilizados en varios tests
# ---------------------------------------------------------------------------


def _pt(x: float, y: float) -> Point2D:
    return Point2D(x=x, y=y)


def _rect_polygon(w: float, h: float) -> Polygon2D:
    """Rectángulo de w×h con esquina inferior izquierda en el origen."""
    return Polygon2D(
        points=[_pt(0.0, 0.0), _pt(w, 0.0), _pt(w, h), _pt(0.0, h)]
    )


def _valid_wall(
    wall_id: str = "W01",
    start: tuple[float, float] = (0.0, 0.0),
    end: tuple[float, float] = (5.0, 0.0),
    wall_type: WallType = WallType.EXTERIOR,
) -> Wall:
    return Wall(
        id=wall_id,
        start_point=_pt(*start),
        end_point=_pt(*end),
        height_m=3.0,
        thickness_m=0.3,
        wall_type=wall_type,
    )


def _valid_space(space_id: str = "SP01", w: float = 4.0, h: float = 5.0) -> Space:
    return Space(
        id=space_id,
        name="Salón",
        contour=_rect_polygon(w, h),
        floor_level=0,
        room_type=RoomType.LIVING,
    )


def _valid_slab(slab_id: str = "SL01") -> Slab:
    return Slab(
        id=slab_id,
        contour=_rect_polygon(10.0, 8.0),
        elevation_m=0.0,
        thickness_m=0.25,
        slab_type=SlabType.FLOOR,
    )


def _valid_storey(storey_id: str = "PB", level: int = 0) -> Storey:
    return Storey(
        id=storey_id,
        level=level,
        elevation_m=0.0,
        height_m=3.0,
        name="Planta Baja",
    )


# ---------------------------------------------------------------------------
# TestWall
# ---------------------------------------------------------------------------


class TestWall:
    def test_rejects_zero_length_wall(self) -> None:
        """Muro con start_point == end_point debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Wall(
                id="W00",
                start_point=_pt(2.0, 3.0),
                end_point=_pt(2.0, 3.0),
                height_m=3.0,
                thickness_m=0.2,
                wall_type=WallType.INTERIOR,
            )

    def test_rejects_zero_height(self) -> None:
        """height_m = 0 debe fallar."""
        with pytest.raises(ValidationError):
            Wall(
                id="W01",
                start_point=_pt(0.0, 0.0),
                end_point=_pt(5.0, 0.0),
                height_m=0.0,
                thickness_m=0.2,
                wall_type=WallType.EXTERIOR,
            )

    def test_rejects_negative_thickness(self) -> None:
        """thickness_m < 0 debe fallar."""
        with pytest.raises(ValidationError):
            Wall(
                id="W01",
                start_point=_pt(0.0, 0.0),
                end_point=_pt(5.0, 0.0),
                height_m=3.0,
                thickness_m=-0.1,
                wall_type=WallType.PARTITION,
            )

    def test_accepts_diagonal_wall(self) -> None:
        """Muros no axiales (diagonales) son válidos."""
        w = _valid_wall(end=(3.0, 4.0))
        assert w.wall_type == WallType.EXTERIOR

    def test_accepts_all_wall_types(self) -> None:
        """Todos los WallType deben poder instanciarse."""
        for wt in WallType:
            w = _valid_wall(wall_id=f"W_{wt}", wall_type=wt)
            assert w.wall_type == wt


# ---------------------------------------------------------------------------
# TestOpening
# ---------------------------------------------------------------------------


class TestOpening:
    def test_rejects_position_above_one(self) -> None:
        """position_along_wall_m > 1.0 debe fallar."""
        with pytest.raises(ValidationError):
            Opening(
                id="O01",
                host_wall_id="W01",
                position_along_wall_m=1.1,
                width_m=0.9,
                height_m=2.1,
                sill_height_m=0.0,
                opening_type=OpeningType.DOOR,
            )

    def test_rejects_negative_position(self) -> None:
        """position_along_wall_m < 0 debe fallar."""
        with pytest.raises(ValidationError):
            Opening(
                id="O01",
                host_wall_id="W01",
                position_along_wall_m=-0.1,
                width_m=0.9,
                height_m=2.1,
                sill_height_m=0.0,
                opening_type=OpeningType.DOOR,
            )

    def test_rejects_zero_width(self) -> None:
        """width_m = 0 debe fallar."""
        with pytest.raises(ValidationError):
            Opening(
                id="O01",
                host_wall_id="W01",
                position_along_wall_m=0.5,
                width_m=0.0,
                height_m=1.2,
                sill_height_m=0.9,
                opening_type=OpeningType.WINDOW,
            )

    def test_rejects_negative_sill_height(self) -> None:
        """sill_height_m < 0 debe fallar."""
        with pytest.raises(ValidationError):
            Opening(
                id="O01",
                host_wall_id="W01",
                position_along_wall_m=0.5,
                width_m=1.2,
                height_m=1.2,
                sill_height_m=-0.1,
                opening_type=OpeningType.WINDOW,
            )

    def test_accepts_door_at_wall_start(self) -> None:
        """Puerta en position=0.0 (inicio del muro) es válida."""
        o = Opening(
            id="O01",
            host_wall_id="W01",
            position_along_wall_m=0.0,
            width_m=0.9,
            height_m=2.1,
            sill_height_m=0.0,
            opening_type=OpeningType.DOOR,
        )
        assert o.opening_type == OpeningType.DOOR

    def test_accepts_window_at_midpoint(self) -> None:
        """Ventana en position=0.5 con alféizar es válida."""
        o = Opening(
            id="O02",
            host_wall_id="W01",
            position_along_wall_m=0.5,
            width_m=1.2,
            height_m=1.2,
            sill_height_m=0.9,
            opening_type=OpeningType.WINDOW,
        )
        assert o.sill_height_m == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# TestSlab
# ---------------------------------------------------------------------------


class TestSlab:
    def test_rejects_zero_thickness(self) -> None:
        """thickness_m = 0 debe fallar."""
        with pytest.raises(ValidationError):
            Slab(
                id="SL01",
                contour=_rect_polygon(10.0, 8.0),
                elevation_m=0.0,
                thickness_m=0.0,
                slab_type=SlabType.GROUND_FLOOR,
            )

    def test_accepts_negative_elevation(self) -> None:
        """Un forjado bajo rasante (elevation_m < 0) es válido."""
        slab = Slab(
            id="SL_SOT",
            contour=_rect_polygon(10.0, 8.0),
            elevation_m=-3.2,
            thickness_m=0.3,
            slab_type=SlabType.FLOOR,
        )
        assert slab.elevation_m == pytest.approx(-3.2)

    def test_accepts_all_slab_types(self) -> None:
        """Todos los SlabType deben poder instanciarse."""
        for st in SlabType:
            slab = _valid_slab()
            slab = Slab(
                id=f"SL_{st}",
                contour=_rect_polygon(8.0, 6.0),
                elevation_m=0.0,
                thickness_m=0.25,
                slab_type=st,
            )
            assert slab.slab_type == st


# ---------------------------------------------------------------------------
# TestSpace
# ---------------------------------------------------------------------------


class TestSpace:
    def test_net_area_m2_rectangle(self) -> None:
        """net_area_m2 de un rectángulo 4×5 debe ser 20.0 m²."""
        space = _valid_space(w=4.0, h=5.0)
        assert space.net_area_m2 == pytest.approx(20.0)

    def test_net_area_m2_triangle(self) -> None:
        """net_area_m2 de un triángulo rectángulo 3-4-5 debe ser 6.0 m²."""
        space = Space(
            id="SP_TRI",
            name="Triángulo",
            contour=Polygon2D(
                points=[_pt(0.0, 0.0), _pt(3.0, 0.0), _pt(0.0, 4.0)]
            ),
            floor_level=0,
            room_type=RoomType.CORRIDOR,
        )
        assert space.net_area_m2 == pytest.approx(6.0)

    def test_net_area_m2_is_positive_regardless_of_winding(self) -> None:
        """net_area_m2 debe ser positiva aunque el contorno sea en sentido horario."""
        space_cw = Space(
            id="SP_CW",
            name="Horario",
            contour=Polygon2D(
                # sentido horario (área con signo negativa en shoelace)
                points=[_pt(0.0, 0.0), _pt(0.0, 5.0), _pt(4.0, 5.0), _pt(4.0, 0.0)]
            ),
            floor_level=1,
            room_type=RoomType.BEDROOM,
        )
        assert space_cw.net_area_m2 == pytest.approx(20.0)

    def test_accepts_optional_typology_id(self) -> None:
        """typology_id es None por defecto y puede asignarse libremente."""
        s = _valid_space()
        assert s.typology_id is None
        s2 = Space(
            id="SP02",
            name="Dormitorio",
            contour=_rect_polygon(3.0, 4.0),
            floor_level=1,
            typology_id="T2",
            room_type=RoomType.BEDROOM,
        )
        assert s2.typology_id == "T2"

    def test_accepts_negative_floor_level(self) -> None:
        """Espacios en planta sótano (floor_level negativo) son válidos."""
        s = Space(
            id="SP_SOT",
            name="Trastero",
            contour=_rect_polygon(2.0, 3.0),
            floor_level=-1,
            room_type=RoomType.STORAGE,
        )
        assert s.floor_level == -1


# ---------------------------------------------------------------------------
# TestStorey
# ---------------------------------------------------------------------------


class TestStorey:
    def test_rejects_zero_height(self) -> None:
        """height_m = 0 debe fallar."""
        with pytest.raises(ValidationError):
            Storey(
                id="PB",
                level=0,
                elevation_m=0.0,
                height_m=0.0,
                name="Planta Baja",
            )

    def test_accepts_underground_storey(self) -> None:
        """Planta con nivel negativo y cota negativa es válida (sótano)."""
        s = Storey(
            id="SOT",
            level=-1,
            elevation_m=-3.0,
            height_m=2.8,
            name="Sótano",
        )
        assert s.level == -1

    def test_storey_aggregates_elements(self) -> None:
        """Una planta con espacios, muros y forjados debe construirse correctamente."""
        storey = Storey(
            id="P1",
            level=1,
            elevation_m=3.0,
            height_m=3.0,
            name="Primera Planta",
            spaces=[_valid_space()],
            walls=[_valid_wall()],
            slabs=[_valid_slab()],
        )
        assert len(storey.spaces) == 1
        assert len(storey.walls) == 1
        assert len(storey.slabs) == 1


# ---------------------------------------------------------------------------
# TestCommunicationCore
# ---------------------------------------------------------------------------


class TestCommunicationCore:
    def test_rejects_empty_serves_floors(self) -> None:
        """serves_floors debe tener al menos una planta."""
        with pytest.raises(ValidationError):
            CommunicationCore(
                position=_pt(5.0, 5.0),
                width_m=4.0,
                depth_m=6.0,
                has_elevator=True,
                serves_floors=[],
            )

    def test_rejects_duplicate_serves_floors(self) -> None:
        """No se permiten niveles duplicados en serves_floors."""
        with pytest.raises(ValidationError):
            CommunicationCore(
                position=_pt(5.0, 5.0),
                width_m=4.0,
                depth_m=6.0,
                has_elevator=True,
                serves_floors=[0, 1, 1],
            )

    def test_accepts_valid_core(self) -> None:
        """Un núcleo con dimensiones positivas y plantas únicas es válido."""
        core = CommunicationCore(
            position=_pt(3.0, 4.0),
            width_m=4.0,
            depth_m=6.0,
            has_elevator=False,
            serves_floors=[0, 1, 2],
        )
        assert core.position.x == pytest.approx(3.0)
        assert core.serves_floors == [0, 1, 2]


class TestParkingSpace:
    def test_rejects_wrong_dimensions_for_type(self) -> None:
        """Una plaza accesible no puede usar dimensiones de plaza estándar."""
        with pytest.raises(ValidationError):
            ParkingSpace(
                id="PK-01",
                contour=_rect_polygon(2.5, 5.0),
                floor_level=-1,
                dimensions=ParkingDimensions(width_m=2.5, depth_m=5.0),
                type=ParkingSpaceType.ACCESSIBLE,
                lane_id="L1",
            )

    def test_accepts_standard_space(self) -> None:
        """Una plaza estándar con dimensiones normativas es válida."""
        space = ParkingSpace(
            id="PK-02",
            contour=_rect_polygon(2.5, 5.0),
            floor_level=-1,
            dimensions=ParkingDimensions(width_m=2.5, depth_m=5.0),
            type=ParkingSpaceType.STANDARD,
            lane_id="L1",
        )
        assert space.room_type == RoomType.PARKING


class TestParkingLane:
    def test_rejects_lane_with_one_point(self) -> None:
        """Un carril debe tener al menos dos puntos en su eje."""
        with pytest.raises(ValidationError):
            ParkingLane(id="L1", points=[_pt(0.0, 0.0)])


class TestParkingStorey:
    def test_rejects_non_underground_level(self) -> None:
        """ParkingStorey debe estar bajo rasante."""
        with pytest.raises(ValidationError):
            ParkingStorey(
                id="PK-ST",
                level=0,
                elevation_m=0.0,
                height_m=3.0,
                name="Parking",
                lanes=[ParkingLane(id="L1", points=[_pt(0.0, 0.0), _pt(10.0, 0.0)])],
                ramp_access=RampAccess(
                    id="R1",
                    start_point=_pt(0.0, 0.0),
                    end_point=_pt(0.0, 10.0),
                    width_m=3.5,
                    slope_pct=15.0,
                    connected_lane_id="L1",
                ),
            )

    def test_accepts_valid_parking_storey(self) -> None:
        """Una planta subterránea con plazas, carriles y rampa es válida."""
        storey = ParkingStorey(
            id="PK-ST",
            level=-1,
            elevation_m=-3.0,
            height_m=3.0,
            name="Parking",
            spaces=[
                ParkingSpace(
                    id="PK-03",
                    contour=_rect_polygon(2.5, 5.0),
                    floor_level=-1,
                    dimensions=ParkingDimensions(width_m=2.5, depth_m=5.0),
                    type=ParkingSpaceType.STANDARD,
                    lane_id="L1",
                )
            ],
            lanes=[ParkingLane(id="L1", points=[_pt(0.0, 0.0), _pt(10.0, 0.0)])],
            ramp_access=RampAccess(
                id="R1",
                start_point=_pt(0.0, 0.0),
                end_point=_pt(0.0, 10.0),
                width_m=3.5,
                slope_pct=15.0,
                connected_lane_id="L1",
            ),
        )
        assert len(storey.spaces) == 1


# ---------------------------------------------------------------------------
# TestBuilding
# ---------------------------------------------------------------------------


class TestBuilding:
    def test_rejects_duplicate_storey_levels(self) -> None:
        """Dos plantas con el mismo nivel deben levantar ValidationError."""
        with pytest.raises(ValidationError):
            Building(
                id="B01",
                name="Edificio test",
                project_id="P1",
                solar_id="S1",
                storeys=[
                    _valid_storey("PB", level=0),
                    _valid_storey("PB2", level=0),
                ],
            )

    def test_accepts_empty_storeys(self) -> None:
        """Un edificio sin plantas todavía (nueva entrada) es válido."""
        b = Building(
            id="B01",
            name="Edificio vacío",
            project_id="P1",
            solar_id="S1",
        )
        assert b.storeys == []

    def test_accepts_metadata_with_mixed_types(self) -> None:
        """metadata acepta strings, ints y floats."""
        b = Building(
            id="B02",
            name="Con metadata",
            project_id="P1",
            solar_id="S1",
            metadata={
                "architect": "Ana García",
                "year": 2026,
                "gross_area_m2": 1200.5,
                "cadastral_ref": None,
            },
        )
        assert b.metadata["year"] == 2026

    def test_accepts_multi_storey_building(self) -> None:
        """Edificio con varias plantas en niveles distintos es válido."""
        b = Building(
            id="B03",
            name="Plurifamiliar",
            project_id="P1",
            solar_id="S1",
            storeys=[
                _valid_storey("PB", level=0),
                _valid_storey("P1", level=1),
                _valid_storey("P2", level=2),
            ],
        )
        assert len(b.storeys) == 3

    def test_accepts_communication_cores(self) -> None:
        """El building debe poder incluir núcleos de comunicación vertical."""
        b = Building(
            id="B04",
            name="Con núcleos",
            project_id="P1",
            solar_id="S1",
            storeys=[_valid_storey("PB", level=0), _valid_storey("P1", level=1)],
            communication_cores=[
                CommunicationCore(
                    position=_pt(6.0, 8.0),
                    width_m=4.0,
                    depth_m=6.0,
                    has_elevator=True,
                    serves_floors=[0, 1],
                )
            ],
        )
        assert len(b.communication_cores) == 1
