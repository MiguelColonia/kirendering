"""
Fixtures de casos válidos para los tests de schemas y del solver.

Usan la API actual de cimiento.schemas (Pydantic v2, nuevos nombres de campo).
Estas fixtures son la fuente de verdad compartida entre test_schemas.py y los
futuros tests del solver; no deben incluir lógica de negocio.
"""

import pytest

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


@pytest.fixture
def sample_typology_t2() -> Typology:
    """Tipología T2 estándar: salón, cocina, 2 dormitorios, 1 baño; 70–90 m² útiles."""
    return Typology(
        id="T2",
        name="Vivienda dos dormitorios",
        min_useful_area=70.0,
        max_useful_area=90.0,
        num_bedrooms=2,
        num_bathrooms=1,
        rooms=[
            Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.5),
            Room(type=RoomType.KITCHEN, min_area=10.0, min_short_side=2.5),
            Room(type=RoomType.BEDROOM, min_area=12.0, min_short_side=2.8),
            Room(type=RoomType.BEDROOM, min_area=10.0, min_short_side=2.5),
            Room(type=RoomType.BATHROOM, min_area=4.0, min_short_side=1.5),
        ],
    )


@pytest.fixture
def sample_solar_rectangular() -> Solar:
    """Solar rectangular de 20×30 m (600 m²), norte alineado con el eje Y, altura máx. 9 m."""
    return Solar(
        id="solar-rectangular-20x30",
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
def sample_program_10_t2(sample_typology_t2: Typology) -> Program:
    """Programa de 1 planta con 10 unidades de tipología T2."""
    return Program(
        project_id="proyecto-ejemplo",
        num_floors=1,
        floor_height_m=3.0,
        typologies=[sample_typology_t2],
        mix=[TypologyMix(typology_id="T2", count=10)],
    )
