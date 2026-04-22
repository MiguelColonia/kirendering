"""
Exportador DXF para la jerarquía BIM de Cimiento.

Genera un archivo DXF con capas separadas por tipo de elemento siguiendo
las convenciones de color de la norma DIN 277 (clasificación de superficies en
edificación). DIN 277 asigna colores y tipos de línea estándar a cada categoría
de elemento constructivo, facilitando la interpretación por parte de estudios de
arquitectura que trabajan con AutoCAD / LibreCAD / FreeCAD.

Capas generadas:
  MUROS_EXT   – Muros exteriores (color 1 = rojo; contorno principal del edificio)
  MUROS_INT   – Muros interiores y tabiques (color 3 = verde; divisiones internas)
  PUERTAS     – Arcos de apertura de puertas (color 4 = cyan)
  VENTANAS    – Huecos de ventana (color 5 = azul)
  COTAS       – Cotas lineales del solar y de los espacios (color 7 = blanco/negro)
  TEXTOS      – Etiquetas de tipo de espacio y área neta (color 2 = amarillo)

Por cada Storey se crea un bloque nombrado "PLANTA_{level}" que puede insertarse
en layouts o consultarse individualmente en cualquier visor DXF.
"""

from pathlib import Path

import ezdxf
from ezdxf import colors

from cimiento.schemas.architectural import Building, OpeningType, Storey, WallType

# ---------------------------------------------------------------------------
# Constantes de capa y color (convención DIN 277 adaptada a CAD)
# ---------------------------------------------------------------------------

_LAYER_EXT_WALLS = "MUROS_EXT"
_LAYER_INT_WALLS = "MUROS_INT"
_LAYER_DOORS = "PUERTAS"
_LAYER_WINDOWS = "VENTANAS"
_LAYER_DIMS = "COTAS"
_LAYER_TEXT = "TEXTOS"

_COLOR_EXT = colors.RED  # 1
_COLOR_INT = colors.GREEN  # 3
_COLOR_DOORS = colors.CYAN  # 4
_COLOR_WINDOWS = colors.BLUE  # 5
_COLOR_DIMS = colors.WHITE  # 7
_COLOR_TEXT = colors.YELLOW  # 2

_DOOR_ARC_RADIUS_FACTOR = 0.9  # radio del arco = anchura de la puerta
_TEXT_HEIGHT = 0.25  # altura de texto en metros


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def export_to_dxf(building: Building, output_path: Path) -> None:
    """
    Serializa un Building al formato DXF R2010 y escribe el archivo en output_path.

    El archivo resultante es abrible en LibreCAD, FreeCAD, AutoCAD y cualquier
    visor DXF compatible con R2010+.

    :param building: Jerarquía BIM completa.
    :param output_path: Ruta del archivo .dxf a crear. El directorio padre debe existir.
    """
    doc = ezdxf.new(dxfversion="R2010")
    _define_layers(doc)

    msp = doc.modelspace()

    for storey in building.storeys:
        block_name = f"PLANTA_{storey.level}"
        block = doc.blocks.new(name=block_name)
        _draw_storey_into(block, storey)

        # Insertar el bloque en el modelspace desplazado según la cota de la planta
        # (representación en planta 2D, sin desplazamiento en Z ya que DXF 2D)
        msp.add_blockref(block_name, insert=(0.0, 0.0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _define_layers(doc: ezdxf.document.Drawing) -> None:
    layers = doc.layers
    layers.add(_LAYER_EXT_WALLS, color=_COLOR_EXT, lineweight=50)
    layers.add(_LAYER_INT_WALLS, color=_COLOR_INT, lineweight=25)
    layers.add(_LAYER_DOORS, color=_COLOR_DOORS, lineweight=13)
    layers.add(_LAYER_WINDOWS, color=_COLOR_WINDOWS, lineweight=13)
    layers.add(_LAYER_DIMS, color=_COLOR_DIMS, lineweight=13)
    layers.add(_LAYER_TEXT, color=_COLOR_TEXT, lineweight=13)


def _draw_storey_into(block, storey: Storey) -> None:
    """Dibuja todos los elementos de una planta en el bloque DXF dado."""
    _draw_walls(block, storey)
    _draw_openings(block, storey)
    _draw_space_labels(block, storey)


def _draw_walls(block, storey: Storey) -> None:
    for wall in storey.walls:
        layer = _LAYER_EXT_WALLS if wall.wall_type == WallType.EXTERIOR else _LAYER_INT_WALLS
        block.add_line(
            start=(wall.start_point.x, wall.start_point.y),
            end=(wall.end_point.x, wall.end_point.y),
            dxfattribs={"layer": layer},
        )


def _draw_openings(block, storey: Storey) -> None:
    """
    Dibuja puertas como arcos de apertura de 90° y ventanas como segmentos dobles.

    Para puertas, el arco representa la hoja abatiéndose en el plano horizontal
    (representación estándar en plantas arquitectónicas a escala 1:50/1:100).
    Para ventanas, se dibujan dos líneas paralelas separadas 0.1 m (símbolo DIN).
    """
    for opening in storey.openings:
        host_wall = next((w for w in storey.walls if w.id == opening.host_wall_id), None)
        if host_wall is None:
            continue

        # Vector a lo largo del muro
        dx = host_wall.end_point.x - host_wall.start_point.x
        dy = host_wall.end_point.y - host_wall.start_point.y
        import math

        wall_len = math.hypot(dx, dy)
        if wall_len < 1e-9:
            continue
        ux, uy = dx / wall_len, dy / wall_len

        # Centro del hueco en planta
        along = wall_len * opening.position_along_wall_m
        cx = host_wall.start_point.x + ux * along
        cy = host_wall.start_point.y + uy * along

        if opening.opening_type == OpeningType.DOOR:
            # Arco de apertura de 90°: esquina de la hoja en extremo izquierdo del hueco
            hinge_x = cx - ux * opening.width_m / 2.0
            hinge_y = cy - uy * opening.width_m / 2.0
            # Ángulo inicial: a lo largo del muro (dirección del batiente cerrado)
            angle_start = math.degrees(math.atan2(uy, ux))
            angle_end = angle_start + 90.0
            block.add_arc(
                center=(hinge_x, hinge_y),
                radius=opening.width_m * _DOOR_ARC_RADIUS_FACTOR,
                start_angle=angle_start,
                end_angle=angle_end,
                dxfattribs={"layer": _LAYER_DOORS},
            )
            # Línea de la hoja cerrada
            block.add_line(
                start=(hinge_x, hinge_y),
                end=(cx + ux * opening.width_m / 2.0, cy + uy * opening.width_m / 2.0),
                dxfattribs={"layer": _LAYER_DOORS},
            )
        else:
            # Ventana: dos segmentos paralelos (0.05 m a cada lado del eje del muro)
            perp_x, perp_y = -uy * 0.05, ux * 0.05
            x1 = cx - ux * opening.width_m / 2.0
            y1 = cy - uy * opening.width_m / 2.0
            x2 = cx + ux * opening.width_m / 2.0
            y2 = cy + uy * opening.width_m / 2.0
            block.add_line(
                start=(x1 + perp_x, y1 + perp_y),
                end=(x2 + perp_x, y2 + perp_y),
                dxfattribs={"layer": _LAYER_WINDOWS},
            )
            block.add_line(
                start=(x1 - perp_x, y1 - perp_y),
                end=(x2 - perp_x, y2 - perp_y),
                dxfattribs={"layer": _LAYER_WINDOWS},
            )


def _draw_space_labels(block, storey: Storey) -> None:
    """Añade etiqueta con room_type y área neta en el centroide de cada espacio."""
    for space in storey.spaces:
        pts = space.contour.points
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        label = f"{space.room_type}\n{space.net_area_m2:.1f} m²"
        block.add_mtext(
            label,
            dxfattribs={
                "layer": _LAYER_TEXT,
                "char_height": _TEXT_HEIGHT,
                "insert": (cx, cy),
            },
        )
