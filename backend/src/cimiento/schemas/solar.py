"""
Representación del solar (terreno) como entidad urbanística.

El Solar encapsula tanto la geometría del terreno (contorno en planta)
como las condiciones normativas básicas que acotan el volumen edificable.
Es la entrada geográfica principal del solver.
"""

from pydantic import BaseModel, Field

from cimiento.schemas.geometry_primitives import Polygon2D


class Solar(BaseModel):
    """
    Terreno edificable con su contorno y condiciones urbanísticas.

    El contorno se expresa como un Polygon2D en el sistema de referencia local
    del proyecto (metros). El ángulo norte y la altura máxima condicionan tanto
    la orientación del edificio como su volumetría.
    """

    id: str = Field(..., description="Identificador único del solar dentro del proyecto")
    contour: Polygon2D = Field(
        ...,
        description=(
            "Polígono que define el contorno del terreno en metros, "
            "en el sistema de referencia local del proyecto"
        ),
    )
    north_angle_deg: float = Field(
        0.0,
        ge=0.0,
        lt=360.0,
        description=(
            "Ángulo del norte geográfico en grados sexagesimales, "
            "medido desde el eje Y positivo del plano en sentido antihorario"
        ),
    )
    max_buildable_height_m: float = Field(
        ...,
        gt=0.0,
        description="Altura máxima edificable en metros según la normativa urbanística aplicable",
    )
