import pytest

from cimiento.schemas import Point2D, Solar


@pytest.fixture
def solar_rectangular_30x30() -> Solar:
    """Solar cuadrado de 30×30 m (900 m²), suficiente para 10 T2 de 70 m².

    Nota: un solar de 20×30 m (600 m²) no puede albergar 10 unidades de 70 m² (700 m²),
    ya que la suma de áreas supera la superficie disponible.
    """
    return Solar(
        polygon=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=30.0, y=0.0),
            Point2D(x=30.0, y=30.0),
            Point2D(x=0.0, y=30.0),
        ],
        north_angle=0.0,
        max_height=9.0,
    )


@pytest.fixture
def solar_5x5() -> Solar:
    """Solar mínimo de 5×5 m; insuficiente para cualquier programa residencial estándar."""
    return Solar(
        polygon=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=5.0, y=0.0),
            Point2D(x=5.0, y=5.0),
            Point2D(x=0.0, y=5.0),
        ],
        north_angle=0.0,
        max_height=9.0,
    )
