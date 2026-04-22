"""
Primitivas geométricas 2D usadas como bloques de construcción por el resto de schemas.

Estas clases representan conceptos geométricos puros sin semántica arquitectónica.
Son inmutables y validadas estrictamente; cualquier cálculo sobre ellas corresponde
a la capa Geometry, no a estos schemas.
"""

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Point2D(BaseModel):
    """Punto en el plano cartesiano, expresado en metros."""

    model_config = ConfigDict(strict=True, frozen=True)

    x: float = Field(..., description="Coordenada X en metros")
    y: float = Field(..., description="Coordenada Y en metros")

    @field_validator("x", "y")
    @classmethod
    def must_be_finite(cls, v: float) -> float:
        """Rechaza NaN e infinito; las coordenadas deben ser valores reales finitos."""
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Las coordenadas deben ser valores finitos (no NaN ni infinito)")
        return v


class Polygon2D(BaseModel):
    """
    Polígono simple en 2D definido por una lista ordenada de vértices.

    El polígono se asume cerrado (el último vértice conecta con el primero).
    No se admiten polígonos degenerados (vértices colineales que forman una línea recta).
    """

    model_config = ConfigDict(strict=True, frozen=True)

    points: list[Point2D] = Field(
        ...,
        min_length=3,
        description="Vértices del polígono en metros, en orden antihorario o horario",
    )

    @model_validator(mode="after")
    def is_not_degenerate(self) -> "Polygon2D":
        """
        Comprueba que el polígono no es degenerado (no todos los vértices son colineales).

        Usa la fórmula de Gauss (shoelace) para calcular el área con signo.
        Si el área es nula el polígono se reduce a una línea recta y no es válido.
        """
        pts = self.points
        n = len(pts)
        signed_area = math.fsum(
            pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y for i in range(n)
        )
        if abs(signed_area) < 1e-9:
            raise ValueError(
                "El polígono es degenerado: todos los vértices son colineales "
                "(el área calculada es cero)"
            )
        return self

    @property
    def bounding_box(self) -> tuple[float, float, float, float]:
        """Devuelve (min_x, min_y, max_x, max_y) de la caja delimitadora axialmente alineada."""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


class Rectangle(BaseModel):
    """
    Rectángulo axialmente alineado definido por su esquina inferior izquierda y sus dimensiones.

    Se usa como bounding box de colocaciones dentro de la solución del solver.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    x: float = Field(..., description="Coordenada X de la esquina inferior izquierda en metros")
    y: float = Field(..., description="Coordenada Y de la esquina inferior izquierda en metros")
    width: float = Field(..., gt=0.0, description="Ancho del rectángulo en metros (debe ser > 0)")
    height: float = Field(..., gt=0.0, description="Alto del rectángulo en metros (debe ser > 0)")

    @field_validator("x", "y")
    @classmethod
    def origin_must_be_finite(cls, v: float) -> float:
        """Rechaza NaN e infinito en las coordenadas de origen."""
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Las coordenadas de origen deben ser valores finitos")
        return v

    @property
    def area(self) -> float:
        """Superficie del rectángulo en m²."""
        return self.width * self.height
