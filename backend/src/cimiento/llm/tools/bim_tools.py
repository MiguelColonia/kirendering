"""
Herramienta de construcción y exportación BIM para el agente copiloto.

Combina geometry.builder y bim.ifc_exporter en una operación atómica que produce
un archivo IFC4 a partir de la solución activa del proyecto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cimiento.bim.ifc_exporter import ValidationResult, export_to_ifc, validate_ifc
from cimiento.geometry.builder import build_building_from_solution
from cimiento.schemas.program import Program
from cimiento.schemas.solar import Solar
from cimiento.schemas.solution import ParkingSolution, Solution


class ExportResult(BaseModel):
    """Resultado de la herramienta build_and_export_ifc."""

    output_path: str = Field(..., description="Ruta absoluta del archivo IFC generado")
    is_valid_ifc: bool = Field(..., description="True si el IFC pasó la validación de ifcopenshell")
    validation_message: str = Field(..., description="Mensaje de validación o confirmación")
    num_storeys: int = Field(..., description="Número de plantas exportadas")
    num_spaces: int = Field(..., description="Número de espacios (viviendas) exportados")


def build_and_export_ifc(
    solar: Solar,
    program: Program,
    solution: Solution,
    output_dir: Path,
    project_id: str,
    parking_solution: ParkingSolution | None = None,
) -> ExportResult:
    """
    Construye el modelo BIM desde la solución activa y lo exporta a IFC4.

    Ejecuta en secuencia:
    1. geometry.builder.build_building_from_solution → Building
    2. bim.ifc_exporter.export_to_ifc → archivo .ifc
    3. bim.ifc_exporter.validate_ifc → comprobación de integridad

    Parámetros
    ----------
    solar:
        Terreno del proyecto activo.
    program:
        Programa del proyecto activo.
    solution:
        Solución producida por el solver (debe tener status OPTIMAL o FEASIBLE).
    output_dir:
        Directorio donde se guardará el archivo IFC.
    project_id:
        Identificador del proyecto; se usa para nombrar el archivo.
    parking_solution:
        Solución de aparcamiento opcional; si se proporciona se incluye en el modelo.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{project_id}.ifc"

    building = build_building_from_solution(solar, program, solution, parking_solution)
    export_to_ifc(building, output_path)

    validation: ValidationResult = validate_ifc(output_path)

    num_storeys = len(building.storeys)
    num_spaces = sum(len(s.spaces) for s in building.storeys)

    if validation.valid:
        val_message = (
            f"IFC válido: {validation.num_buildings} edificio(s), "
            f"{validation.num_storeys} planta(s), {validation.num_spaces} espacio(s)."
        )
    else:
        warnings_str = "; ".join(validation.warnings) if validation.warnings else "sin detalles"
        val_message = f"IFC inválido: {warnings_str}"

    return ExportResult(
        output_path=str(output_path.resolve()),
        is_valid_ifc=validation.valid,
        validation_message=val_message,
        num_storeys=num_storeys,
        num_spaces=num_spaces,
    )


# ---------------------------------------------------------------------------
# Definición en formato Ollama para tool-calling
# ---------------------------------------------------------------------------

BUILD_AND_EXPORT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "build_and_export_ifc",
        "description": (
            "Construye el modelo BIM completo a partir de la distribución calculada y lo exporta "
            "a un archivo IFC4 listo para abrir en Revit, ArchiCAD o cualquier visor IFC. "
            "Requiere que se haya ejecutado solve_distribution previamente. "
            "Úsala cuando el arquitecto pida generar el modelo, "
            "exportar a IFC o descargar el proyecto."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}
