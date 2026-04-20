import pytest

from cimiento.schemas import Program, Room, RoomType, Typology


@pytest.fixture
def typology_t2() -> Typology:
    """Tipología T2 estándar: 2 dormitorios, 70–90 m²."""
    return Typology(
        id="T2",
        name="Vivienda dos dormitorios",
        min_area=70.0,
        max_area=90.0,
        bedrooms=2,
        bathrooms=1,
        required_rooms=[
            Room(room_type=RoomType.LIVING, min_area=20.0, min_short_side=3.5),
            Room(room_type=RoomType.KITCHEN, min_area=10.0, min_short_side=2.5),
            Room(room_type=RoomType.BEDROOM, min_area=12.0, min_short_side=2.8),
            Room(room_type=RoomType.BEDROOM, min_area=10.0, min_short_side=2.5),
            Room(room_type=RoomType.BATHROOM, min_area=4.0, min_short_side=1.5),
        ],
    )


@pytest.fixture
def program_10_t2(typology_t2: Typology) -> Program:
    """Programa de 10 viviendas T2 en 1 planta, superficie edificable suficiente."""
    return Program(
        typology_mix={typology_t2.id: 10},
        total_buildable_area=900.0,
        num_floors=1,
    )


@pytest.fixture
def program_10_t2_infeasible(typology_t2: Typology) -> Program:
    """Programa de 10 viviendas T2 que no cabe en un solar de 5×5 m."""
    return Program(
        typology_mix={typology_t2.id: 10},
        total_buildable_area=700.0,
        num_floors=1,
    )
