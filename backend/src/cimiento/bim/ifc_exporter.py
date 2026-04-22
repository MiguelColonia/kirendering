"""
Exportador IFC4 para la jerarquía BIM de Cimiento.

== Decisiones de diseño ==

IFC4 frente a IFC2x3
--------------------
Usamos IFC4 (publicado en 2013) porque es el estándar actual mantenido por
buildingSMART. IFC2x3 solo se justifica si un cliente concreto lo requiere para
interoperabilidad con software legado; en ese caso, el punto de cambio es la línea
``ifcopenshell.file(schema='IFC4')``.

IfcWallStandardCase frente a IfcWall
-------------------------------------
IfcWallStandardCase exige que el muro sea un prisma recto de sección constante
(exactamente lo que modela nuestro schema Wall). Esta subclase semántica permite
que Revit, ArchiCAD y BIMcollab infieran automáticamente el espesor, la dirección
del eje y las uniones de esquina sin análisis geométrico adicional. IfcWall es más
genérico y correcto para muros de forma libre, pero sacrifica interoperabilidad.

IfcOpeningElement y void-cutting
---------------------------------
En IFC, un hueco físico se modela como:
  IfcOpeningElement → vacia un muro (IfcRelVoidsElement)
  IfcDoor/IfcWindow → rellena el IfcOpeningElement (IfcRelFillsElement)
Esta implementación crea los IfcDoor/IfcWindow con posición correcta y los
asocia al Storey. El IfcOpeningElement con corte geométrico booleano es un TODO
para Fase 3 (requiere transformación 3D del sistema de referencia del muro).

TODO Fase 3: crear IfcOpeningElement con geometría de caja, usar
feature.add_feature(model, feature=opening_elem, element=wall) para aplicar el
corte booleano y feature.add_filling para asociar la puerta/ventana.

IfcFurniture
-------------
No generamos mobiliario porque en fase de anteproyecto la distribución funcional
es abstracta. El mobiliario se introduce en fase de proyecto básico con programa
detallado por espacio. Añadirlo ahora contaminaría el modelo IFC con datos no
respaldados por el programa de necesidades.

Coordenadas y unidades
-----------------------
Todas las cotas son en metros (SI). El proyecto usa IfcSIUnit METRE para longitudes.
Las matrices de placement son 4×4 en numpy float64, columna 3 es la traslación.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.guid
import numpy as np

from cimiento.schemas.architectural import (
    Building,
    CommunicationCore,
    Opening,
    OpeningType,
    ParkingSpace,
    Slab,
    SlabType,
    Space,
    Storey,
    Wall,
)

# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Resultado de la validación de un archivo IFC."""

    valid: bool
    num_buildings: int = 0
    num_storeys: int = 0
    num_walls: int = 0
    num_spaces: int = 0
    num_slabs: int = 0
    num_doors: int = 0
    num_windows: int = 0
    num_stairs: int = 0
    num_transport_elements: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Función pública: exportación
# ---------------------------------------------------------------------------


def export_to_ifc(building: Building, output_path: Path) -> None:
    """
    Serializa un Building al formato IFC4 y escribe el archivo en output_path.

    El archivo resultante es abrible en BlenderBIM (Blender addon gratuito),
    BIMvision, Solibri, FreeCAD y cualquier visor IFC compatible con IFC4.

    :param building: Jerarquía BIM completa generada por geometry.builder.
    :param output_path: Ruta del archivo .ifc a crear; los directorios padre
        deben existir. Si el archivo ya existe se sobreescribe.
    """
    model = _create_ifc_project(building)

    body_ctx = _get_body_context(model)
    ifc_storey_map = {}  # storey.id → IfcBuildingStorey

    ifc_building = model.by_type("IfcBuilding")[0]

    for storey in building.storeys:
        ifc_storey = _export_storey(model, ifc_building, storey, body_ctx)
        ifc_storey_map[storey.id] = ifc_storey

        wall_ifc_map: dict[str, object] = {}  # wall.id → IfcWallStandardCase
        for wall in storey.walls:
            ifc_wall = _export_wall(model, ifc_storey, wall, storey.elevation_m, body_ctx)
            wall_ifc_map[wall.id] = ifc_wall

        for slab in storey.slabs:
            _export_slab(model, ifc_storey, slab, body_ctx)

        for space in storey.spaces:
            _export_space(model, ifc_storey, space, storey.elevation_m, storey.height_m, body_ctx)

        for opening in storey.openings:
            host_wall = wall_ifc_map.get(opening.host_wall_id)
            wall_schema = next((w for w in storey.walls if w.id == opening.host_wall_id), None)
            if host_wall and wall_schema:
                _export_opening(
                    model,
                    ifc_storey,
                    opening,
                    wall_schema,
                    storey.elevation_m,
                    body_ctx,
                )

        for idx, core in enumerate(building.communication_cores):
            if storey.level in core.serves_floors:
                _export_communication_core(
                    model=model,
                    ifc_storey=ifc_storey,
                    core=core,
                    storey=storey,
                    core_idx=idx,
                    body_ctx=body_ctx,
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(output_path))


# ---------------------------------------------------------------------------
# Función pública: validación
# ---------------------------------------------------------------------------


def validate_ifc(path: Path) -> ValidationResult:
    """
    Reabre un archivo IFC con IfcOpenShell y comprueba su integridad básica.

    No realiza validación de schema completa (para eso existe ifcopenshell-validate);
    solo verifica que el archivo es parseable y reporta conteos de entidades principales.
    """
    if not path.exists():
        return ValidationResult(valid=False, warnings=[f"Archivo no encontrado: {path}"])

    try:
        model = ifcopenshell.open(str(path))
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(valid=False, warnings=[f"Error al abrir IFC: {exc}"])

    warnings: list[str] = []

    num_buildings = len(model.by_type("IfcBuilding"))
    num_storeys = len(model.by_type("IfcBuildingStorey"))
    num_walls = len(model.by_type("IfcWallStandardCase")) + len(model.by_type("IfcWall"))
    num_spaces = len(model.by_type("IfcSpace"))
    num_slabs = len(model.by_type("IfcSlab"))
    num_doors = len(model.by_type("IfcDoor"))
    num_windows = len(model.by_type("IfcWindow"))
    num_stairs = len(model.by_type("IfcStair"))
    num_transport_elements = len(model.by_type("IfcTransportElement"))

    if num_buildings == 0:
        warnings.append("No se encontró ningún IfcBuilding")
    if num_storeys == 0:
        warnings.append("No se encontró ningún IfcBuildingStorey")
    if num_walls == 0:
        warnings.append("No se encontró ningún muro IFC")

    return ValidationResult(
        valid=True,
        num_buildings=num_buildings,
        num_storeys=num_storeys,
        num_walls=num_walls,
        num_spaces=num_spaces,
        num_slabs=num_slabs,
        num_doors=num_doors,
        num_windows=num_windows,
        num_stairs=num_stairs,
        num_transport_elements=num_transport_elements,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers de inicialización del modelo IFC
# ---------------------------------------------------------------------------


def _create_ifc_project(building: Building) -> ifcopenshell.file:
    """Crea el archivo IFC4 con proyecto, unidades, sitio y edificio."""
    model = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcProject", name=building.name
    )
    # Unidades métricas SI: metros para longitud, metros cuadrados para área
    ifcopenshell.api.run("unit.assign_unit", model, length={"is_metric": True, "raw": "METRES"})

    # Contexto de representación geométrica 3D
    model_ctx = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_ctx,
    )

    # IfcSite con georreferenciación básica (sin coordenadas reales; TODO Fase 4: integrar
    # referencia catastral y sistema de coordenadas del proyecto)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Solar")
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])

    ifc_building = ifcopenshell.api.run(
        "root.create_entity",
        model,
        ifc_class="IfcBuilding",
        name=building.name,
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", model, relating_object=site, products=[ifc_building]
    )

    return model


def _get_body_context(model: ifcopenshell.file) -> object:
    """Devuelve el IfcGeometricRepresentationSubContext Model/Body/MODEL_VIEW."""
    for ctx in model.by_type("IfcGeometricRepresentationSubContext"):
        if ctx.ContextIdentifier == "Body":
            return ctx
    raise RuntimeError("Body context not found; _create_ifc_project must be called first")


# ---------------------------------------------------------------------------
# Helpers de exportación por tipo de elemento
# ---------------------------------------------------------------------------


def _export_storey(
    model: ifcopenshell.file,
    ifc_building: object,
    storey: Storey,
    body_ctx: object,
) -> object:
    """Crea un IfcBuildingStorey y lo agrega al edificio."""
    ifc_storey = ifcopenshell.api.run(
        "root.create_entity",
        model,
        ifc_class="IfcBuildingStorey",
        name=storey.name,
    )
    # Cota de referencia de la planta
    matrix = np.eye(4)
    matrix[2][3] = storey.elevation_m
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=ifc_storey, matrix=matrix)
    ifcopenshell.api.run(
        "aggregate.assign_object",
        model,
        relating_object=ifc_building,
        products=[ifc_storey],
    )
    return ifc_storey


def _export_wall(
    model: ifcopenshell.file,
    ifc_storey: object,
    wall: Wall,
    elevation_m: float,
    body_ctx: object,
) -> object:
    """
    Crea un IfcWallStandardCase con geometría de extrusión de sección rectangular.

    geometry.create_2pt_wall genera internamente:
    - IfcExtrudedAreaSolid con perfil rectangular (espesor × altura)
    - IfcLocalPlacement con origen en start_point y eje X a lo largo del muro
    """
    ifc_wall = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcWallStandardCase", name=wall.id
    )
    ifcopenshell.api.run(
        "geometry.create_2pt_wall",
        model,
        element=ifc_wall,
        context=body_ctx,
        p1=(wall.start_point.x, wall.start_point.y),
        p2=(wall.end_point.x, wall.end_point.y),
        elevation=elevation_m,
        height=wall.height_m,
        thickness=wall.thickness_m,
        is_si=True,
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=ifc_storey,
        products=[ifc_wall],
    )
    return ifc_wall


def _export_slab(
    model: ifcopenshell.file,
    ifc_storey: object,
    slab: Slab,
    body_ctx: object,
) -> object:
    """
    Crea un IfcSlab con PredefinedType correcto y geometría de extrusión hacia abajo.

    Mapeo de SlabType a IfcSlab PredefinedType:
      GROUND_FLOOR → BASESLAB  (solera / forjado sanitario)
      FLOOR        → FLOOR     (forjado intermedio)
      ROOF         → ROOF      (cubierta)
    """
    predefined_map = {
        SlabType.GROUND_FLOOR: "BASESLAB",
        SlabType.FLOOR: "FLOOR",
        SlabType.ROOF: "ROOF",
    }
    ifc_slab = ifcopenshell.api.run(
        "root.create_entity",
        model,
        ifc_class="IfcSlab",
        name=slab.id,
        predefined_type=predefined_map[slab.slab_type],
    )

    polyline = [(p.x, p.y) for p in slab.contour.points]
    rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        model,
        context=body_ctx,
        depth=slab.thickness_m,
        polyline=polyline,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=ifc_slab, representation=rep
    )

    # Placement en la cota correcta de la cara superior del forjado
    matrix = np.eye(4)
    matrix[2][3] = slab.elevation_m
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=ifc_slab, matrix=matrix)

    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=ifc_storey,
        products=[ifc_slab],
    )
    return ifc_slab


def _export_space(
    model: ifcopenshell.file,
    ifc_storey: object,
    space: Space,
    elevation_m: float,
    height_m: float,
    body_ctx: object,
) -> object:
    """
    Crea un IfcSpace con geometría volumétrica (extrusión del contorno en planta).

    El volumen del espacio es informativo: permite que los viewers calculen área
    y volumen netos directamente del modelo IFC sin consultar propiedades externas.
    """
    create_kwargs = {"ifc_class": "IfcSpace", "name": space.name}
    if isinstance(space, ParkingSpace):
        create_kwargs["predefined_type"] = "PARKING"

    ifc_space = ifcopenshell.api.run("root.create_entity", model, **create_kwargs)

    polyline = [(p.x, p.y) for p in space.contour.points]
    rep = ifcopenshell.api.run(
        "geometry.add_slab_representation",
        model,
        context=body_ctx,
        depth=height_m,
        polyline=polyline,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=ifc_space, representation=rep
    )

    matrix = np.eye(4)
    matrix[2][3] = elevation_m
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=ifc_space, matrix=matrix)

    # IfcSpace es un IfcSpatialElement: se relaciona con el Storey mediante IfcRelAggregates,
    # no IfcRelContainedInSpatialStructure (que es para IfcElement físicos como muros y forjados).
    ifcopenshell.api.run(
        "aggregate.assign_object",
        model,
        relating_object=ifc_storey,
        products=[ifc_space],
    )
    return ifc_space


def _export_opening(
    model: ifcopenshell.file,
    ifc_storey: object,
    opening: Opening,
    wall: Wall,
    elevation_m: float,
    body_ctx: object,
) -> object:
    """
    Crea un IfcDoor o IfcWindow con posición 3D calculada desde los datos del muro.

    Posición del elemento:
    - A lo largo del muro: start_point + pos_relativa × longitud_muro × dir_unitario
    - Vertical: elevation_m + sill_height_m

    La apertura del muro (IfcOpeningElement y corte booleano) es TODO Fase 3:
    requiere transformar el sistema de referencia del muro en IfcLocalPlacement
    y añadir la relación IfcRelVoidsElement / IfcRelFillsElement.
    """
    is_door = opening.opening_type == OpeningType.DOOR
    ifc_class = "IfcDoor" if is_door else "IfcWindow"

    element = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class=ifc_class, name=opening.id
    )

    # Calcular posición 3D del elemento
    dx = wall.end_point.x - wall.start_point.x
    dy = wall.end_point.y - wall.start_point.y
    wall_len = math.hypot(dx, dy)
    ux, uy = (dx / wall_len, dy / wall_len) if wall_len > 1e-9 else (1.0, 0.0)

    # Centro del hueco proyectado en el eje del muro
    along = wall_len * opening.position_along_wall_m
    cx = wall.start_point.x + ux * along
    cy = wall.start_point.y + uy * along
    cz = elevation_m + opening.sill_height_m

    # Placement: origen en esquina inferior izquierda, x a lo largo del muro, z arriba
    # La esquina izquierda retrocede media anchura desde el centro
    ox = cx - ux * opening.width_m / 2.0
    oy = cy - uy * opening.width_m / 2.0

    # Perpendicular a la izquierda del muro (apunta fuera de la habitación por convención)
    perp_x, perp_y = -uy, ux

    matrix = np.array(
        [
            [ux, perp_x, 0.0, ox],
            [uy, perp_y, 0.0, oy],
            [0.0, 0.0, 1.0, cz],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    ifcopenshell.api.run("geometry.edit_object_placement", model, product=element, matrix=matrix)

    # Geometría del hueco usando la API de puerta o ventana
    if is_door:
        rep = ifcopenshell.api.run(
            "geometry.add_door_representation",
            model,
            context=body_ctx,
            overall_height=opening.height_m,
            overall_width=opening.width_m,
        )
    else:
        rep = ifcopenshell.api.run(
            "geometry.add_window_representation",
            model,
            context=body_ctx,
            overall_height=opening.height_m,
            overall_width=opening.width_m,
        )

    if rep is not None:
        ifcopenshell.api.run(
            "geometry.assign_representation", model, product=element, representation=rep
        )

    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=ifc_storey,
        products=[element],
    )
    return element


def _export_communication_core(
    model: ifcopenshell.file,
    ifc_storey: object,
    core: CommunicationCore,
    storey: Storey,
    core_idx: int,
    body_ctx: object,
) -> None:
    """Exporta núcleo vertical como IfcStair y, opcionalmente, IfcTransportElement."""

    def _assign_prismatic_geometry(product: object) -> None:
        rep = ifcopenshell.api.run(
            "geometry.add_slab_representation",
            model,
            context=body_ctx,
            depth=storey.height_m,
            polyline=[
                (0.0, 0.0),
                (core.width_m, 0.0),
                (core.width_m, core.depth_m),
                (0.0, core.depth_m),
            ],
        )
        ifcopenshell.api.run(
            "geometry.assign_representation",
            model,
            product=product,
            representation=rep,
        )
        matrix = np.eye(4)
        matrix[0][3] = core.position.x
        matrix[1][3] = core.position.y
        matrix[2][3] = storey.elevation_m
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=product,
            matrix=matrix,
        )

    stair = ifcopenshell.api.run(
        "root.create_entity",
        model,
        ifc_class="IfcStair",
        name=f"core-{core_idx}-stair-{storey.level}",
    )
    _assign_prismatic_geometry(stair)
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=ifc_storey,
        products=[stair],
    )

    if core.has_elevator:
        elevator = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcTransportElement",
            name=f"core-{core_idx}-elevator-{storey.level}",
        )
        _assign_prismatic_geometry(elevator)
        ifcopenshell.api.run(
            "spatial.assign_container",
            model,
            relating_structure=ifc_storey,
            products=[elevator],
        )
