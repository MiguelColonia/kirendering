"""
Tests de contrato para los schemas de cimiento.

Verifican que las restricciones de validación están correctamente definidas:
rechazo de valores inválidos, aceptación de casos límite correctos y comportamiento
de propiedades calculadas. No prueban lógica del solver ni de geometría computacional.
"""

import math

import pytest
from pydantic import ValidationError

from cimiento.schemas import (
    Point2D,
    Polygon2D,
    Program,
    Rectangle,
    Room,
    RoomType,
    Solar,
    Solution,
    SolutionMetrics,
    SolutionStatus,
    Typology,
    TypologyMix,
    UnitPlacement,
)

pytest_plugins = ["tests.fixtures.valid_cases"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _square_polygon() -> Polygon2D:
    """Cuadrado 4×3 m centrado en el origen; usado como contorno auxiliar."""
    return Polygon2D(
        points=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=4.0, y=0.0),
            Point2D(x=4.0, y=3.0),
            Point2D(x=0.0, y=3.0),
        ]
    )


def _minimal_typology(rooms: list[Room] | None = None) -> Typology:
    """Tipología mínima válida con un salón; usada como base para tests de Typology."""
    return Typology(
        id="T1",
        name="Tipología mínima",
        min_useful_area=40.0,
        max_useful_area=60.0,
        num_bedrooms=1,
        num_bathrooms=1,
        rooms=rooms
        if rooms is not None
        else [Room(type=RoomType.LIVING, min_area=15.0, min_short_side=3.0)],
    )


# ---------------------------------------------------------------------------
# TestPoint2D
# ---------------------------------------------------------------------------


class TestPoint2D:
    def test_rejects_nan_x(self) -> None:
        """x=NaN debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Point2D(x=float("nan"), y=0.0)

    def test_rejects_nan_y(self) -> None:
        """y=NaN debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Point2D(x=0.0, y=float("nan"))

    def test_rejects_inf_x(self) -> None:
        """x=+Inf debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Point2D(x=math.inf, y=0.0)

    def test_rejects_negative_inf_y(self) -> None:
        """y=-Inf debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Point2D(x=0.0, y=-math.inf)

    def test_accepts_valid_coordinates(self) -> None:
        """Coordenadas finitas válidas no deben lanzar excepción."""
        p = Point2D(x=-5.0, y=100.5)
        assert p.x == -5.0
        assert p.y == 100.5


# ---------------------------------------------------------------------------
# TestPolygon2D
# ---------------------------------------------------------------------------


class TestPolygon2D:
    def test_rejects_two_points(self) -> None:
        """Una lista de solo 2 puntos no forma un polígono."""
        with pytest.raises(ValidationError):
            Polygon2D(points=[Point2D(x=0.0, y=0.0), Point2D(x=1.0, y=0.0)])

    def test_rejects_one_point(self) -> None:
        """Una lista de 1 punto no forma un polígono."""
        with pytest.raises(ValidationError):
            Polygon2D(points=[Point2D(x=0.0, y=0.0)])

    def test_rejects_collinear_points_horizontal(self) -> None:
        """Tres puntos sobre la misma línea horizontal (área = 0) deben fallar."""
        with pytest.raises(ValidationError):
            Polygon2D(
                points=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=1.0, y=0.0),
                    Point2D(x=2.0, y=0.0),
                ]
            )

    def test_rejects_collinear_points_diagonal(self) -> None:
        """Tres puntos sobre la misma diagonal (área = 0) deben fallar."""
        with pytest.raises(ValidationError):
            Polygon2D(
                points=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=1.0, y=1.0),
                    Point2D(x=2.0, y=2.0),
                ]
            )

    def test_bounding_box_square(self) -> None:
        """bounding_box de un rectángulo 4×3 debe ser (0, 0, 4, 3)."""
        poly = _square_polygon()
        assert poly.bounding_box == (0.0, 0.0, 4.0, 3.0)

    def test_bounding_box_with_negative_coords(self) -> None:
        """bounding_box funciona correctamente con coordenadas negativas."""
        poly = Polygon2D(
            points=[
                Point2D(x=-3.0, y=-2.0),
                Point2D(x=5.0, y=-2.0),
                Point2D(x=5.0, y=4.0),
                Point2D(x=-3.0, y=4.0),
            ]
        )
        assert poly.bounding_box == (-3.0, -2.0, 5.0, 4.0)

    def test_accepts_triangle(self) -> None:
        """Un triángulo no degenerado debe ser aceptado."""
        poly = Polygon2D(
            points=[
                Point2D(x=0.0, y=0.0),
                Point2D(x=4.0, y=0.0),
                Point2D(x=2.0, y=3.0),
            ]
        )
        assert len(poly.points) == 3


# ---------------------------------------------------------------------------
# TestRectangle
# ---------------------------------------------------------------------------


class TestRectangle:
    def test_rejects_negative_width(self) -> None:
        """width < 0 debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Rectangle(x=0.0, y=0.0, width=-1.0, height=5.0)

    def test_rejects_zero_width(self) -> None:
        """width = 0 debe levantar ValidationError (se requiere > 0)."""
        with pytest.raises(ValidationError):
            Rectangle(x=0.0, y=0.0, width=0.0, height=5.0)

    def test_rejects_negative_height(self) -> None:
        """height < 0 debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Rectangle(x=0.0, y=0.0, width=5.0, height=-1.0)

    def test_rejects_zero_height(self) -> None:
        """height = 0 debe levantar ValidationError (se requiere > 0)."""
        with pytest.raises(ValidationError):
            Rectangle(x=0.0, y=0.0, width=5.0, height=0.0)

    def test_area_calculation(self) -> None:
        """area debe devolver width × height."""
        r = Rectangle(x=1.0, y=2.0, width=3.0, height=4.0)
        assert r.area == pytest.approx(12.0)

    def test_area_non_square(self) -> None:
        """area es correcta para rectángulos no cuadrados."""
        r = Rectangle(x=0.0, y=0.0, width=7.0, height=10.0)
        assert r.area == pytest.approx(70.0)

    def test_rejects_nan_origin(self) -> None:
        """Coordenada de origen NaN debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Rectangle(x=float("nan"), y=0.0, width=5.0, height=5.0)


# ---------------------------------------------------------------------------
# TestRoom
# ---------------------------------------------------------------------------


class TestRoom:
    def test_rejects_zero_min_area(self) -> None:
        """min_area = 0 debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Room(type=RoomType.BEDROOM, min_area=0.0, min_short_side=2.0)

    def test_rejects_negative_min_area(self) -> None:
        """min_area < 0 debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Room(type=RoomType.BEDROOM, min_area=-5.0, min_short_side=2.0)

    def test_rejects_zero_min_short_side(self) -> None:
        """min_short_side = 0 debe levantar ValidationError."""
        with pytest.raises(ValidationError):
            Room(type=RoomType.KITCHEN, min_area=10.0, min_short_side=0.0)

    def test_accepts_valid_room(self) -> None:
        """Room con valores positivos debe construirse sin errores."""
        r = Room(type=RoomType.BATHROOM, min_area=4.0, min_short_side=1.5)
        assert r.type == RoomType.BATHROOM


# ---------------------------------------------------------------------------
# TestTypology
# ---------------------------------------------------------------------------


class TestTypology:
    def test_rejects_without_living_room(self) -> None:
        """Tipología sin ningún Room de tipo LIVING debe fallar."""
        with pytest.raises(ValidationError):
            Typology(
                id="T0",
                name="Sin salón",
                min_useful_area=40.0,
                max_useful_area=60.0,
                num_bedrooms=1,
                num_bathrooms=1,
                rooms=[Room(type=RoomType.BEDROOM, min_area=12.0, min_short_side=2.5)],
            )

    def test_rejects_empty_rooms(self) -> None:
        """Lista de rooms vacía también debe fallar (no contiene LIVING)."""
        with pytest.raises(ValidationError):
            Typology(
                id="T0",
                name="Vacía",
                min_useful_area=40.0,
                max_useful_area=60.0,
                num_bedrooms=0,
                num_bathrooms=1,
                rooms=[],
            )

    def test_rejects_min_area_equal_to_max(self) -> None:
        """min_useful_area == max_useful_area debe fallar (se requiere estrictamente menor)."""
        with pytest.raises(ValidationError):
            _minimal_typology.__wrapped__ if hasattr(_minimal_typology, "__wrapped__") else None
            Typology(
                id="T1",
                name="Igual",
                min_useful_area=70.0,
                max_useful_area=70.0,
                num_bedrooms=1,
                num_bathrooms=1,
                rooms=[Room(type=RoomType.LIVING, min_area=15.0, min_short_side=3.0)],
            )

    def test_rejects_min_area_greater_than_max(self) -> None:
        """min_useful_area > max_useful_area debe fallar."""
        with pytest.raises(ValidationError):
            Typology(
                id="T1",
                name="Invertida",
                min_useful_area=90.0,
                max_useful_area=70.0,
                num_bedrooms=1,
                num_bathrooms=1,
                rooms=[Room(type=RoomType.LIVING, min_area=15.0, min_short_side=3.0)],
            )

    def test_accepts_valid_typology(self, sample_typology_t2: Typology) -> None:
        """Tipología T2 de referencia debe construirse sin errores."""
        assert sample_typology_t2.id == "T2"
        assert any(r.type == RoomType.LIVING for r in sample_typology_t2.rooms)


# ---------------------------------------------------------------------------
# TestSolar
# ---------------------------------------------------------------------------


class TestSolar:
    def test_rejects_north_angle_360(self) -> None:
        """north_angle_deg = 360 debe fallar (rango es [0, 360), exclusivo en 360)."""
        with pytest.raises(ValidationError):
            Solar(
                id="s1",
                contour=_square_polygon(),
                north_angle_deg=360.0,
                max_buildable_height_m=9.0,
            )

    def test_rejects_negative_north_angle(self) -> None:
        """north_angle_deg negativo debe fallar."""
        with pytest.raises(ValidationError):
            Solar(
                id="s1",
                contour=_square_polygon(),
                north_angle_deg=-1.0,
                max_buildable_height_m=9.0,
            )

    def test_rejects_zero_height(self) -> None:
        """max_buildable_height_m = 0 debe fallar (se requiere > 0)."""
        with pytest.raises(ValidationError):
            Solar(
                id="s1",
                contour=_square_polygon(),
                north_angle_deg=0.0,
                max_buildable_height_m=0.0,
            )

    def test_rejects_negative_height(self) -> None:
        """max_buildable_height_m < 0 debe fallar."""
        with pytest.raises(ValidationError):
            Solar(
                id="s1",
                contour=_square_polygon(),
                north_angle_deg=0.0,
                max_buildable_height_m=-3.0,
            )

    def test_accepts_max_angle_just_below_360(self) -> None:
        """north_angle_deg = 359.9 es el valor máximo válido."""
        s = Solar(
            id="s1",
            contour=_square_polygon(),
            north_angle_deg=359.9,
            max_buildable_height_m=9.0,
        )
        assert s.north_angle_deg == pytest.approx(359.9)

    def test_accepts_valid_solar(self, sample_solar_rectangular: Solar) -> None:
        """Solar de referencia 20×30 m debe construirse sin errores."""
        assert sample_solar_rectangular.id == "solar-rectangular-20x30"


# ---------------------------------------------------------------------------
# TestProgram
# ---------------------------------------------------------------------------


class TestProgram:
    def test_rejects_zero_floors(self, sample_typology_t2: Typology) -> None:
        """num_floors = 0 debe fallar (se requiere >= 1)."""
        with pytest.raises(ValidationError):
            Program(
                project_id="p1",
                num_floors=0,
                floor_height_m=3.0,
                typologies=[sample_typology_t2],
                mix=[TypologyMix(typology_id="T2", count=5)],
            )

    def test_rejects_unknown_typology_in_mix(self, sample_typology_t2: Typology) -> None:
        """Un typology_id en mix que no existe en typologies debe fallar."""
        with pytest.raises(ValidationError):
            Program(
                project_id="p1",
                num_floors=1,
                floor_height_m=3.0,
                typologies=[sample_typology_t2],
                mix=[TypologyMix(typology_id="T9_INEXISTENTE", count=3)],
            )

    def test_rejects_zero_floor_height(self, sample_typology_t2: Typology) -> None:
        """floor_height_m = 0 debe fallar."""
        with pytest.raises(ValidationError):
            Program(
                project_id="p1",
                num_floors=1,
                floor_height_m=0.0,
                typologies=[sample_typology_t2],
                mix=[TypologyMix(typology_id="T2", count=1)],
            )

    def test_valid_program_passes(self, sample_program_10_t2: Program) -> None:
        """Program de referencia con mix consistente debe construirse sin errores."""
        assert sample_program_10_t2.project_id == "proyecto-ejemplo"
        assert len(sample_program_10_t2.mix) == 1
        assert sample_program_10_t2.mix[0].typology_id == "T2"
        assert sample_program_10_t2.mix[0].count == 10

    def test_mix_typology_id_matches_typologies(self, sample_program_10_t2: Program) -> None:
        """Todos los typology_id del mix deben existir en typologies."""
        known_ids = {t.id for t in sample_program_10_t2.typologies}
        for entry in sample_program_10_t2.mix:
            assert entry.typology_id in known_ids


# ---------------------------------------------------------------------------
# TestSolution
# ---------------------------------------------------------------------------


class TestSolution:
    def _valid_metrics(self) -> SolutionMetrics:
        return SolutionMetrics(
            total_assigned_area=0.0,
            num_units_placed=0,
            typology_fulfillment={},
        )

    def test_unit_placement_rejects_negative_floor(self) -> None:
        """floor < 0 en UnitPlacement debe fallar."""
        with pytest.raises(ValidationError):
            UnitPlacement(
                typology_id="T2",
                floor=-1,
                bbox=Rectangle(x=0.0, y=0.0, width=7.0, height=10.0),
            )

    def test_infeasible_with_empty_placements_is_valid(self) -> None:
        """Solution INFEASIBLE con lista vacía de placements debe ser válida."""
        sol = Solution(
            status=SolutionStatus.INFEASIBLE,
            placements=[],
            metrics=self._valid_metrics(),
            solver_time_seconds=0.5,
            message="El solar es insuficiente para el programa solicitado",
        )
        assert sol.status == SolutionStatus.INFEASIBLE
        assert sol.placements == []
        assert sol.message is not None

    def test_solution_message_optional_for_optimal(self) -> None:
        """Solution OPTIMAL no necesita message (campo opcional)."""
        sol = Solution(
            status=SolutionStatus.OPTIMAL,
            placements=[],
            metrics=SolutionMetrics(
                total_assigned_area=700.0,
                num_units_placed=10,
                typology_fulfillment={"T2": 1.0},
            ),
            solver_time_seconds=1.2,
        )
        assert sol.message is None

    def test_rejects_negative_solver_time(self) -> None:
        """solver_time_seconds < 0 debe fallar."""
        with pytest.raises(ValidationError):
            Solution(
                status=SolutionStatus.ERROR,
                placements=[],
                metrics=self._valid_metrics(),
                solver_time_seconds=-1.0,
            )
