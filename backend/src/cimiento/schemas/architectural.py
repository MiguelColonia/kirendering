"""
Schemas de la jerarquía BIM arquitectónica de Cimiento.

Representan los elementos físicos del edificio tal como los entiende IFC:
muros como segmentos extruidos, aperturas como huevos en el muro anfitrión,
forjados como superficies con espesor, espacios como recintos delimitados y
plantas como contenedores lógicos de todos esos elementos.

La jerarquía es:
    Building → Storey → {Space, Wall, Slab}
                Wall  → Opening (hueco de puerta o ventana)

Estos schemas son el contrato entre el solver (que produce UnitPlacement con
bboxes abstractos) y la capa BIM (que los convierte a geometría IFC real).
"""

import math
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from cimiento.schemas.geometry_primitives import Point2D, Polygon2D
from cimiento.schemas.typology import RoomType

# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------


class WallType(StrEnum):
    """Clasificación estructural y funcional del muro dentro del edificio."""

    EXTERIOR = "EXTERIOR"
    """Muro de fachada o medianera; define el perímetro del edificio."""

    INTERIOR = "INTERIOR"
    """Muro de separación entre viviendas o entre unidades y zonas comunes."""

    PARTITION = "PARTITION"
    """Tabique interior ligero dentro de una misma unidad."""

    STRUCTURAL = "STRUCTURAL"
    """Muro portante que transmite cargas a la cimentación."""


class OpeningType(StrEnum):
    """Tipo de hueco practicado en un muro."""

    DOOR = "DOOR"
    WINDOW = "WINDOW"


class SlabType(StrEnum):
    """Posición del forjado dentro de la sección vertical del edificio."""

    GROUND_FLOOR = "GROUND_FLOOR"
    """Solera o forjado sanitario en contacto con el terreno."""

    FLOOR = "FLOOR"
    """Forjado intermedio entre plantas."""

    ROOF = "ROOF"
    """Cubierta o forjado de coronación."""


# ---------------------------------------------------------------------------
# Wall
# ---------------------------------------------------------------------------


class Wall(BaseModel):
    """
    Muro representado como segmento 2D con espesor y altura de extrusión.

    Se modela como un segmento y no como un polígono porque IFC (IfcWallStandardCase)
    define los muros exactamente así: eje central, espesor y altura de extrusión.
    Esta representación evita la duplicación de vértices en esquinas y simplifica
    la generación de la geometría IFC en la capa BIM.
    """

    id: str = Field(..., description="Identificador único del muro dentro de la planta")
    start_point: Point2D = Field(..., description="Extremo de inicio del eje central del muro")
    end_point: Point2D = Field(..., description="Extremo final del eje central del muro")
    height_m: float = Field(
        ...,
        gt=0.0,
        description="Altura de extrusión del muro en metros",
    )
    thickness_m: float = Field(
        ...,
        gt=0.0,
        description="Espesor del muro en metros, medido perpendicularmente al eje",
    )
    wall_type: WallType = Field(..., description="Clasificación estructural y funcional del muro")

    @model_validator(mode="after")
    def endpoints_are_distinct(self) -> "Wall":
        """Impide muros de longitud cero (inicio y final coincidentes)."""
        if self.start_point.x == self.end_point.x and self.start_point.y == self.end_point.y:
            raise ValueError(
                f"El muro '{self.id}' tiene longitud cero: "
                "start_point y end_point son el mismo punto"
            )
        return self


# ---------------------------------------------------------------------------
# Opening
# ---------------------------------------------------------------------------


class Opening(BaseModel):
    """
    Hueco (puerta o ventana) practicado en un muro anfitrión.

    La posición se expresa como valor relativo en [0, 1] respecto a la longitud del muro
    en lugar de coordenadas absolutas. Razón: si el muro se desplaza o redimensiona,
    la posición relativa sigue siendo semánticamente correcta sin recalcular nada.
    Las coordenadas absolutas se derivan en la capa BIM a partir de start_point,
    end_point y este valor relativo.
    """

    id: str = Field(..., description="Identificador único del hueco")
    host_wall_id: str = Field(
        ...,
        description="Identificador del muro que contiene este hueco (debe existir en la planta)",
    )
    position_along_wall_m: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Posición relativa del centro del hueco a lo largo del muro: "
            "0.0 = extremo start_point, 1.0 = extremo end_point"
        ),
    )
    width_m: float = Field(..., gt=0.0, description="Anchura del hueco en metros")
    height_m: float = Field(..., gt=0.0, description="Altura del hueco en metros")
    sill_height_m: float = Field(
        ...,
        ge=0.0,
        description=(
            "Altura del umbral (alféizar) sobre el nivel de suelo de la planta en metros; "
            "0.0 para puertas"
        ),
    )
    opening_type: OpeningType = Field(..., description="Tipo de hueco: puerta o ventana")

    @field_validator("sill_height_m")
    @classmethod
    def sill_below_opening_top(cls, v: float) -> float:
        """El alféizar puede ser cero o positivo; la validación cruzada con height_m
        requiere un model_validator si se necesitase en el futuro."""
        return v


# ---------------------------------------------------------------------------
# Slab
# ---------------------------------------------------------------------------


class Slab(BaseModel):
    """
    Forjado horizontal definido por un contorno poligonal, una cota y un espesor.

    Corresponde a IfcSlab en la jerarquía IFC. El contorno representa la proyección
    en planta del forjado; la geometría 3D se obtiene extrudiendo ese contorno
    hacia abajo en thickness_m desde elevation_m.
    """

    id: str = Field(..., description="Identificador único del forjado")
    contour: Polygon2D = Field(
        ...,
        description="Proyección en planta del forjado en el sistema de referencia del proyecto",
    )
    elevation_m: float = Field(
        ...,
        description=(
            "Cota de la cara superior del forjado en metros sobre el nivel de referencia (0.0)"
        ),
    )
    thickness_m: float = Field(
        ...,
        gt=0.0,
        description="Espesor del forjado en metros",
    )
    slab_type: SlabType = Field(
        ...,
        description="Posición del forjado en la sección vertical del edificio",
    )


# ---------------------------------------------------------------------------
# Space
# ---------------------------------------------------------------------------


class Space(BaseModel):
    """
    Espacio arquitectónico delimitado por un contorno poligonal en planta.

    Corresponde a IfcSpace en IFC. Representa un recinto funcional (salón, dormitorio,
    pasillo…) dentro de una planta del edificio. La propiedad net_area_m2 se calcula
    geométricamente a partir del contorno sin almacenarse, garantizando consistencia
    ante modificaciones del polígono.
    """

    id: str = Field(..., description="Identificador único del espacio")
    name: str = Field(..., description="Nombre descriptivo del espacio, p. ej. 'Salón-Comedor'")
    contour: Polygon2D = Field(
        ...,
        description="Contorno del espacio en planta, en el sistema de referencia de la planta",
    )
    floor_level: int = Field(
        ...,
        description=(
            "Número de planta a la que pertenece el espacio "
            "(negativo para plantas bajo rasante, 0 para planta baja)"
        ),
    )
    typology_id: str | None = Field(
        default=None,
        description=(
            "Identificador de la tipología de vivienda a la que pertenece este espacio; "
            "None para espacios comunes o sin clasificar"
        ),
    )
    room_type: RoomType = Field(
        ...,
        description="Tipo funcional del espacio según la clasificación de RoomType",
    )

    @property
    def net_area_m2(self) -> float:
        """
        Superficie neta del espacio en m², calculada mediante la fórmula de Gauss (shoelace).

        El valor es siempre positivo independientemente del sentido de giro del polígono.
        """
        pts = self.contour.points
        n = len(pts)
        signed_area = math.fsum(
            pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y
            for i in range(n)
        )
        return abs(signed_area) / 2.0


# ---------------------------------------------------------------------------
# Storey
# ---------------------------------------------------------------------------


class Storey(BaseModel):
    """
    Planta del edificio: contenedor de espacios, muros y forjados a una cota determinada.

    Corresponde a IfcBuildingStorey. La cota de referencia (elevation_m) es la cara
    superior del forjado de suelo de la planta. La altura (height_m) es la distancia
    hasta el forjado de la planta inmediatamente superior.
    """

    id: str = Field(..., description="Identificador único de la planta")
    level: int = Field(
        ...,
        description=(
            "Número ordinal de la planta: 0 = planta baja, 1 = primera planta, "
            "-1 = planta sótano, etc."
        ),
    )
    elevation_m: float = Field(
        ...,
        description="Cota de la cara superior del forjado de suelo en metros sobre el nivel ±0,00",
    )
    height_m: float = Field(
        ...,
        gt=0.0,
        description="Altura libre de planta en metros (suelo terminado a techo terminado)",
    )
    name: str = Field(
        ...,
        description="Nombre legible de la planta, p. ej. 'Planta Baja' o 'Planta 1'",
    )
    spaces: list[Space] = Field(
        default_factory=list,
        description="Espacios contenidos en esta planta",
    )
    walls: list[Wall] = Field(
        default_factory=list,
        description="Muros definidos en esta planta",
    )
    slabs: list[Slab] = Field(
        default_factory=list,
        description="Forjados (suelo y techo) asociados a esta planta",
    )
    openings: list[Opening] = Field(
        default_factory=list,
        description="Huecos (puertas y ventanas) de los muros de esta planta",
    )


# ---------------------------------------------------------------------------
# CommunicationCore
# ---------------------------------------------------------------------------


class CommunicationCore(BaseModel):
    """
    Núcleo de comunicación vertical (escalera y, opcionalmente, ascensor).

    Se modela como un volumen prismático vertical cuya posición en planta se
    mantiene constante en todas las plantas servidas por el núcleo.
    """

    position: Point2D = Field(
        ...,
        description="Esquina inferior izquierda del núcleo en planta",
    )
    width_m: float = Field(..., gt=0.0, description="Ancho del núcleo en metros")
    depth_m: float = Field(..., gt=0.0, description="Fondo del núcleo en metros")
    has_elevator: bool = Field(
        ...,
        description="Indica si el núcleo incluye ascensor además de la escalera",
    )
    serves_floors: list[int] = Field(
        ...,
        min_length=1,
        description="Lista de niveles de planta servidos por este núcleo",
    )

    @field_validator("serves_floors")
    @classmethod
    def serves_floors_unique(cls, values: list[int]) -> list[int]:
        """Evita niveles duplicados en la lista de plantas servidas."""
        if len(set(values)) != len(values):
            raise ValueError("serves_floors no puede contener niveles duplicados")
        return values


class ParkingSpaceType(StrEnum):
    """Clasificación funcional de plaza de aparcamiento."""

    STANDARD = "STANDARD"
    ACCESSIBLE = "ACCESSIBLE"
    MOTORCYCLE = "MOTORCYCLE"


class ParkingDimensions(BaseModel):
    """Dimensiones normalizadas de una plaza de aparcamiento."""

    width_m: float = Field(..., gt=0.0, description="Ancho útil de la plaza en metros")
    depth_m: float = Field(..., gt=0.0, description="Fondo útil de la plaza en metros")


class ParkingSpace(Space):
    """
    Plaza de aparcamiento representada como un recinto 2D rectangular.

    Hereda de Space para mantener compatibilidad con la jerarquía BIM y con los
    exportadores que recorren storey.spaces de forma genérica.
    """

    name: str = Field(default="Plaza de aparcamiento", description="Nombre legible de la plaza")
    typology_id: str | None = Field(
        default=None,
        description="No aplica a plazas de aparcamiento; se mantiene por compatibilidad",
    )
    room_type: RoomType = Field(
        default=RoomType.PARKING,
        description="Tipo funcional del espacio; para plazas es siempre PARKING",
    )
    dimensions: ParkingDimensions = Field(
        ...,
        description="Dimensiones normativas de la plaza según su tipo",
    )
    type: ParkingSpaceType = Field(..., description="Tipo de plaza: estándar, accesible o moto")
    lane_id: str = Field(..., description="Carril al que se conecta operativamente la plaza")

    @model_validator(mode="after")
    def dimensions_match_type(self) -> "ParkingSpace":
        """Comprueba que las dimensiones coinciden con el catálogo admitido."""
        expected = {
            ParkingSpaceType.STANDARD: (2.5, 5.0),
            ParkingSpaceType.ACCESSIBLE: (3.6, 5.0),
            ParkingSpaceType.MOTORCYCLE: (1.0, 2.5),
        }[self.type]
        if (
            abs(self.dimensions.width_m - expected[0]) > 1e-6
            or abs(self.dimensions.depth_m - expected[1]) > 1e-6
        ):
            raise ValueError(
                f"Dimensiones incompatibles con {self.type}: "
                f"{self.dimensions.width_m}×{self.dimensions.depth_m} m"
            )
        return self


class ParkingLane(BaseModel):
    """Carril de circulación del aparcamiento definido por su eje en planta."""

    id: str = Field(..., description="Identificador único del carril")
    points: list[Point2D] = Field(
        ...,
        min_length=2,
        description="Puntos del eje del carril en planta",
    )
    width_m: float = Field(
        default=5.0,
        gt=0.0,
        description="Anchura útil del carril en metros; 5.0 m para doble sentido",
    )
    connected_lane_ids: list[str] = Field(
        default_factory=list,
        description="Identificadores de carriles conectados a este carril",
    )


class RampAccess(BaseModel):
    """Datos geométricos básicos de la rampa de acceso al aparcamiento."""

    id: str = Field(..., description="Identificador único de la rampa")
    start_point: Point2D = Field(..., description="Punto de inicio de la rampa en planta")
    end_point: Point2D = Field(..., description="Punto final de la rampa en planta")
    width_m: float = Field(..., gt=0.0, description="Anchura libre de la rampa")
    slope_pct: float = Field(..., gt=0.0, description="Pendiente media de la rampa en porcentaje")
    connected_lane_id: str = Field(..., description="Carril del aparcamiento conectado a la rampa")


class ParkingStorey(Storey):
    """Planta subterránea de aparcamiento con plazas, carriles y rampa de acceso."""

    spaces: list[ParkingSpace] = Field(
        default_factory=list,
        description="Plazas de aparcamiento contenidas en la planta",
    )
    lanes: list[ParkingLane] = Field(
        default_factory=list,
        description="Carriles de circulación contenidos en la planta",
    )
    ramp_access: RampAccess = Field(..., description="Datos geométricos de la rampa de acceso")

    @model_validator(mode="after")
    def parking_storey_is_underground(self) -> "ParkingStorey":
        """La planta de aparcamiento debe estar bajo rasante."""
        if self.level >= 0:
            raise ValueError("ParkingStorey debe tener level negativo")
        return self


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


class Building(BaseModel):
    """
    Edificio completo: raíz de la jerarquía BIM del proyecto.

    Corresponde a IfcBuilding. Agrupa todas las plantas y referencia el solar
    y el proyecto al que pertenece. El campo metadata permite añadir atributos
    libres (arquitecto, fecha, referencia catastral…) sin modificar el schema.
    """

    id: str = Field(..., description="Identificador único del edificio")
    name: str = Field(..., description="Nombre del edificio o promoción")
    project_id: str = Field(
        ...,
        description="Identificador del proyecto al que pertenece este edificio",
    )
    solar_id: str = Field(
        ...,
        description="Identificador del solar sobre el que se construye el edificio",
    )
    storeys: list[Storey] = Field(
        default_factory=list,
        description="Plantas del edificio ordenadas por nivel ascendente",
    )
    communication_cores: list[CommunicationCore] = Field(
        default_factory=list,
        description="Núcleos de comunicación vertical del edificio",
    )
    metadata: dict[str, str | int | float | None] = Field(
        default_factory=dict,
        description=(
            "Atributos libres del edificio: architect, date, cadastral_ref, client, etc."
        ),
    )

    @model_validator(mode="after")
    def storey_levels_are_unique(self) -> "Building":
        """Dos plantas no pueden tener el mismo número de nivel."""
        levels = [s.level for s in self.storeys]
        if len(levels) != len(set(levels)):
            duplicates = [lvl for lvl in set(levels) if levels.count(lvl) > 1]
            raise ValueError(
                f"El edificio '{self.id}' tiene plantas con nivel duplicado: {duplicates}"
            )
        return self
