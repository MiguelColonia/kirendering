"""
Programa edificatorio: qué tipologías se quieren construir y en qué cantidad.

El Program es el contrato entre el promotor/arquitecto y el solver.
Contiene tanto la definición completa de las tipologías como el mix
que especifica cuántas unidades de cada tipo se deben colocar.
"""

from pydantic import BaseModel, Field, model_validator

from cimiento.schemas.typology import Typology


class TypologyMix(BaseModel):
    """
    Entrada del mix que asocia una tipología con el número de unidades requeridas.

    Se usa como elemento de la lista Program.mix; separar el conteo de la definición
    permite reutilizar la misma tipología en distintos programas.
    """

    typology_id: str = Field(
        ...,
        description="Identificador de la tipología; debe coincidir con un Typology.id del Program",
    )
    count: int = Field(
        ...,
        ge=1,
        description="Número de unidades de esta tipología que el solver debe colocar",
    )


class Program(BaseModel):
    """
    Programa completo de un proyecto residencial.

    Encapsula todas las tipologías del proyecto y el mix de unidades requeridas.
    El solver recibe un Program y un Solar para producir una Solution.
    """

    project_id: str = Field(
        ...,
        description="Identificador del proyecto al que pertenece el programa",
    )
    num_floors: int = Field(
        ...,
        ge=1,
        description="Número de plantas sobre rasante en las que se distribuirán las viviendas",
    )
    floor_height_m: float = Field(
        ...,
        gt=0.0,
        description="Altura libre de planta en metros; condiciona el volumen edificado total",
    )
    typologies: list[Typology] = Field(
        ...,
        min_length=1,
        description="Definición completa de todas las tipologías que participan en el programa",
    )
    mix: list[TypologyMix] = Field(
        default_factory=list,
        description=(
            "Mix de tipologías: cuántas unidades de cada tipo se deben colocar. "
            "Lista vacía representa un programa sin unidades (el solver devuelve FEASIBLE vacío)."
        ),
    )

    @model_validator(mode="after")
    def mix_references_known_typologies(self) -> "Program":
        """Comprueba que cada typology_id del mix existe en la lista de typologies del programa."""
        known_ids = {t.id for t in self.typologies}
        unknown = [entry.typology_id for entry in self.mix if entry.typology_id not in known_ids]
        if unknown:
            raise ValueError(
                f"El mix referencia tipologías no definidas en el programa: {unknown}. "
                f"Tipologías disponibles: {sorted(known_ids)}"
            )
        return self
