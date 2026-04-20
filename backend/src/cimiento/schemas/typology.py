"""
Tipologías de vivienda y sus estancias constituyentes.

Una Typology define el programa funcional de un tipo de vivienda: superficies mínima
y máxima, número de dormitorios y baños, y la lista de estancias requeridas. El solver
usa estas restricciones para dimensionar cada unidad residencial.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class RoomType(StrEnum):
    """Tipos funcionales de estancia en una vivienda residencial."""

    LIVING = "LIVING"
    KITCHEN = "KITCHEN"
    BEDROOM = "BEDROOM"
    BATHROOM = "BATHROOM"
    CORRIDOR = "CORRIDOR"
    STORAGE = "STORAGE"
    PARKING = "PARKING"


class Room(BaseModel):
    """
    Estancia individual requerida dentro de una tipología.

    Especifica el tipo funcional y las restricciones dimensionales mínimas
    que el solver debe respetar al distribuir el espacio.
    """

    type: RoomType = Field(..., description="Tipo funcional de la estancia")
    min_area: float = Field(
        ...,
        description="Superficie útil mínima de la estancia en m²",
    )
    min_short_side: float = Field(
        ...,
        description=(
            "Longitud mínima del lado más corto del recinto en metros; "
            "garantiza proporciones habitables"
        ),
    )

    @field_validator("min_area")
    @classmethod
    def min_area_positive(cls, v: float) -> float:
        """La superficie mínima debe ser estrictamente positiva."""
        if v <= 0:
            raise ValueError(f"min_area debe ser > 0, recibido: {v}")
        return v

    @field_validator("min_short_side")
    @classmethod
    def min_short_side_positive(cls, v: float) -> float:
        """El lado mínimo debe ser estrictamente positivo."""
        if v <= 0:
            raise ValueError(f"min_short_side debe ser > 0, recibido: {v}")
        return v


class Typology(BaseModel):
    """
    Tipo de vivienda con su programa funcional completo.

    Define el rango de superficies aceptables y la composición de estancias.
    Cada Typology participa en el Program que recibe el solver.
    """

    id: str = Field(..., description="Identificador único de la tipología, p. ej. 'T2'")
    name: str = Field(..., description="Nombre descriptivo de la tipología")
    min_useful_area: float = Field(
        ...,
        gt=0.0,
        description="Superficie útil mínima de la vivienda completa en m²",
    )
    max_useful_area: float = Field(
        ...,
        gt=0.0,
        description="Superficie útil máxima de la vivienda completa en m²",
    )
    num_bedrooms: int = Field(..., ge=0, description="Número de dormitorios de la tipología")
    num_bathrooms: int = Field(..., ge=1, description="Número de baños de la tipología")
    rooms: list[Room] = Field(
        default_factory=list,
        description="Estancias que debe contener la tipología, con sus restricciones",
    )

    @model_validator(mode="after")
    def area_range_is_valid(self) -> "Typology":
        """La superficie mínima debe ser estrictamente menor que la máxima."""
        if self.min_useful_area >= self.max_useful_area:
            raise ValueError(
                f"min_useful_area ({self.min_useful_area}) debe ser "
                f"estrictamente menor que max_useful_area ({self.max_useful_area})"
            )
        return self

    @model_validator(mode="after")
    def has_living_room(self) -> "Typology":
        """Toda tipología residencial debe incluir al menos una estancia de tipo LIVING."""
        if not any(r.type == RoomType.LIVING for r in self.rooms):
            raise ValueError(
                f"La tipología '{self.id}' debe contener al menos una estancia de tipo LIVING"
            )
        return self
