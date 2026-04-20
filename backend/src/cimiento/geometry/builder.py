"""
Módulo de construcción BIM: traduce una Solution del solver en un Building arquitectónico.

La función pública build_building_from_solution recibe los inputs del solver
(Solar + Program + Solution) y produce la jerarquía Building → Storey → {Space, Wall, Slab}
con aperturas (puertas) en los muros generadas automáticamente.

TODO: No genera aparcamiento ni zonas de servidumbre.
TODO: Solo funciona correctamente con muros ortogonales (solar rectangular).
"""

import math
from itertools import combinations

from cimiento.schemas.architectural import (
    Building,
    Opening,
    OpeningType,
    ParkingStorey,
    Slab,
    SlabType,
    Space,
    Storey,
    Wall,
    WallType,
)
from cimiento.schemas.geometry_primitives import Point2D, Polygon2D, Rectangle
from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import ParkingSolution, Solution, UnitPlacement
from cimiento.schemas.typology import RoomType

# ---------------------------------------------------------------------------
# Constantes de diseño
# ---------------------------------------------------------------------------

_DOOR_WIDTH_M = 0.9
_DOOR_HEIGHT_M = 2.1
_EXT_WALL_THICKNESS_M = 0.3
_INT_WALL_THICKNESS_M = 0.15
_SLAB_THICKNESS_M = 0.25
_EPS = 1e-6


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def build_building_from_solution(
    solar: Solar,
    program: Program,
    solution: Solution,
    parking_solution: ParkingSolution | None = None,
) -> Building:
    """
    Traduce una Solution abstracta del solver en un Building arquitectónico.

    Por cada planta del programa produce un Storey con:
    - Un Space por cada UnitPlacement
    - Muros exteriores a lo largo del perímetro del solar
    - Muros interiores en los límites compartidos entre unidades adyacentes
    - Una puerta por Space en el muro adyacente de mayor longitud
    - Forjados de suelo y cubierta con el contorno del solar
    """
    floors: dict[int, list[UnitPlacement]] = {floor: [] for floor in range(program.num_floors)}
    for p in solution.placements:
        floors.setdefault(p.floor, []).append(p)

    typology_map = {t.id: t for t in program.typologies}
    storeys: list[Storey] = []

    if parking_solution and parking_solution.storey is not None:
        parking_storey = parking_solution.storey
        storeys.append(
            ParkingStorey(
                id=parking_storey.id,
                level=parking_storey.level,
                elevation_m=parking_storey.elevation_m,
                height_m=parking_storey.height_m,
                name=parking_storey.name,
                spaces=parking_storey.spaces,
                walls=_build_exterior_walls(solar, parking_storey.height_m, parking_storey.id),
                slabs=_build_slabs(
                    solar,
                    parking_storey.elevation_m,
                    parking_storey.height_m,
                    parking_storey.id,
                ),
                openings=[],
                lanes=parking_storey.lanes,
                ramp_access=parking_storey.ramp_access,
            )
        )

    for floor_level in range(program.num_floors):
        placements = floors.get(floor_level, [])
        storey_id = f"storey-{floor_level}"
        elevation_m = floor_level * program.floor_height_m

        spaces = _build_spaces(placements, floor_level, typology_map, storey_id)
        ext_walls = _build_exterior_walls(solar, program.floor_height_m, storey_id)
        int_walls = _build_interior_walls(placements, program.floor_height_m, storey_id)
        all_walls = ext_walls + int_walls
        openings = _build_openings(placements, all_walls, storey_id)
        slabs = _build_slabs(solar, elevation_m, program.floor_height_m, storey_id)

        storeys.append(
            Storey(
                id=storey_id,
                level=floor_level,
                elevation_m=elevation_m,
                height_m=program.floor_height_m,
                name="Planta Baja" if floor_level == 0 else f"Planta {floor_level}",
                spaces=spaces,
                walls=all_walls,
                slabs=slabs,
                openings=openings,
            )
        )

    return Building(
        id=f"building-{program.project_id}",
        name="Edificio generado",
        project_id=program.project_id,
        solar_id=solar.id,
        storeys=storeys,
        communication_cores=solution.communication_cores,
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _bbox_to_polygon(bbox: Rectangle) -> Polygon2D:
    x, y, w, h = bbox.x, bbox.y, bbox.width, bbox.height
    return Polygon2D(
        points=[
            Point2D(x=x, y=y),
            Point2D(x=x + w, y=y),
            Point2D(x=x + w, y=y + h),
            Point2D(x=x, y=y + h),
        ]
    )


def _build_spaces(
    placements: list[UnitPlacement],
    floor_level: int,
    typology_map: dict,
    storey_id: str,
) -> list[Space]:
    spaces = []
    for i, p in enumerate(placements):
        typology = typology_map.get(p.typology_id)
        name = typology.name if typology else p.typology_id
        spaces.append(
            Space(
                id=f"{storey_id}-sp-{i}",
                name=name,
                contour=_bbox_to_polygon(p.bbox),
                floor_level=floor_level,
                typology_id=p.typology_id,
                room_type=RoomType.LIVING,
            )
        )
    return spaces


def _build_exterior_walls(solar: Solar, height_m: float, storey_id: str) -> list[Wall]:
    pts = solar.contour.points
    n = len(pts)
    return [
        Wall(
            id=f"{storey_id}-ext-{i}",
            start_point=pts[i],
            end_point=pts[(i + 1) % n],
            height_m=height_m,
            thickness_m=_EXT_WALL_THICKNESS_M,
            wall_type=WallType.EXTERIOR,
        )
        for i in range(n)
    ]


def _shared_boundary(a: Rectangle, b: Rectangle) -> tuple[Point2D, Point2D] | None:
    """Devuelve el segmento compartido entre dos rectángulos adyacentes, o None."""
    ax1, ay1 = a.x, a.y
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx1, by1 = b.x, b.y
    bx2, by2 = b.x + b.width, b.y + b.height

    # Frontera vertical compartida (ax2==bx1 o bx2==ax1)
    if abs(ax2 - bx1) < _EPS or abs(bx2 - ax1) < _EPS:
        shared_x = bx1 if abs(ax2 - bx1) < _EPS else ax1
        oy1, oy2 = max(ay1, by1), min(ay2, by2)
        if oy2 - oy1 > _EPS:
            return Point2D(x=shared_x, y=oy1), Point2D(x=shared_x, y=oy2)

    # Frontera horizontal compartida (ay2==by1 o by2==ay1)
    if abs(ay2 - by1) < _EPS or abs(by2 - ay1) < _EPS:
        shared_y = by1 if abs(ay2 - by1) < _EPS else ay1
        ox1, ox2 = max(ax1, bx1), min(ax2, bx2)
        if ox2 - ox1 > _EPS:
            return Point2D(x=ox1, y=shared_y), Point2D(x=ox2, y=shared_y)

    return None


def _build_interior_walls(
    placements: list[UnitPlacement],
    height_m: float,
    storey_id: str,
) -> list[Wall]:
    walls = []
    for idx, (i, j) in enumerate(combinations(range(len(placements)), 2)):
        shared = _shared_boundary(placements[i].bbox, placements[j].bbox)
        if shared is None:
            continue
        p0, p1 = shared
        walls.append(
            Wall(
                id=f"{storey_id}-int-{idx}",
                start_point=p0,
                end_point=p1,
                height_m=height_m,
                thickness_m=_INT_WALL_THICKNESS_M,
                wall_type=WallType.INTERIOR,
            )
        )
    return walls


def _wall_length(wall: Wall) -> float:
    return math.hypot(
        wall.end_point.x - wall.start_point.x,
        wall.end_point.y - wall.start_point.y,
    )


def _walls_adjacent_to_bbox(bbox: Rectangle, walls: list[Wall]) -> list[Wall]:
    """Muros ortogonales que comparten al menos un tramo con el perímetro del bbox."""
    x1, y1 = bbox.x, bbox.y
    x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height
    adjacent = []
    for wall in walls:
        is_h = abs(wall.start_point.y - wall.end_point.y) < _EPS
        is_v = abs(wall.start_point.x - wall.end_point.x) < _EPS
        if is_h:
            wy = wall.start_point.y
            if not (abs(wy - y1) < _EPS or abs(wy - y2) < _EPS):
                continue
            wx1 = min(wall.start_point.x, wall.end_point.x)
            wx2 = max(wall.start_point.x, wall.end_point.x)
            if wx1 < x2 - _EPS and wx2 > x1 + _EPS:
                adjacent.append(wall)
        elif is_v:
            wx = wall.start_point.x
            if not (abs(wx - x1) < _EPS or abs(wx - x2) < _EPS):
                continue
            wy1 = min(wall.start_point.y, wall.end_point.y)
            wy2 = max(wall.start_point.y, wall.end_point.y)
            if wy1 < y2 - _EPS and wy2 > y1 + _EPS:
                adjacent.append(wall)
    return adjacent


def _door_position_along_wall(bbox: Rectangle, wall: Wall) -> float:
    """Posición normalizada [0,1] del centro de la puerta sobre el muro."""
    x1, y1 = bbox.x, bbox.y
    x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height

    is_h = abs(wall.start_point.y - wall.end_point.y) < _EPS
    if is_h:
        wxa, wxb = wall.start_point.x, wall.end_point.x
        lo = max(x1, min(wxa, wxb))
        hi = min(x2, max(wxa, wxb))
        mid = (lo + hi) / 2.0
        denom = wxb - wxa
    else:
        wya, wyb = wall.start_point.y, wall.end_point.y
        lo = max(y1, min(wya, wyb))
        hi = min(y2, max(wya, wyb))
        mid = (lo + hi) / 2.0
        denom = wyb - wya

    if abs(denom) < _EPS:
        return 0.5
    pos = (mid - (wall.start_point.x if is_h else wall.start_point.y)) / denom
    return max(0.0, min(1.0, pos))


def _build_openings(
    placements: list[UnitPlacement],
    walls: list[Wall],
    storey_id: str,
) -> list[Opening]:
    openings = []
    for i, placement in enumerate(placements):
        adjacent = _walls_adjacent_to_bbox(placement.bbox, walls)
        if not adjacent:
            continue
        host = max(adjacent, key=_wall_length)
        pos = _door_position_along_wall(placement.bbox, host)
        openings.append(
            Opening(
                id=f"{storey_id}-door-{i}",
                host_wall_id=host.id,
                position_along_wall_m=pos,
                width_m=_DOOR_WIDTH_M,
                height_m=_DOOR_HEIGHT_M,
                sill_height_m=0.0,
                opening_type=OpeningType.DOOR,
            )
        )
    return openings


def _build_slabs(
    solar: Solar,
    elevation_m: float,
    height_m: float,
    storey_id: str,
) -> list[Slab]:
    floor_type = SlabType.GROUND_FLOOR if abs(elevation_m) < _EPS else SlabType.FLOOR
    return [
        Slab(
            id=f"{storey_id}-slab-floor",
            contour=solar.contour,
            elevation_m=elevation_m,
            thickness_m=_SLAB_THICKNESS_M,
            slab_type=floor_type,
        ),
        Slab(
            id=f"{storey_id}-slab-roof",
            contour=solar.contour,
            elevation_m=elevation_m + height_m,
            thickness_m=_SLAB_THICKNESS_M,
            slab_type=SlabType.ROOF,
        ),
    ]
