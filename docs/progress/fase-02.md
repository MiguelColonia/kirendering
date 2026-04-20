# Fase 2 — Geometría y exportación BIM

**Estado:** Completada  
**Fecha:** 2026-04-20

---

## Qué se logró

### Schemas arquitectónicos (`cimiento.schemas.architectural`)
- `WallType`, `OpeningType`, `SlabType` como StrEnum.
- `Wall`: segmento 2D extruido con validación de longitud no nula.
- `Opening`: hueco con posición relativa [0,1] en el muro host.
- `Slab`: forjado con contorno poligonal y espesor.
- `Space`: espacio con `net_area_m2` calculada por fórmula de Gauss (shoelace).
- `Storey`: contenedor de espacios, muros, forjados y aperturas.
- `Building`: raíz de la jerarquía con validación de niveles únicos.
- 26 tests unitarios de contrato en `test_architectural_schemas.py`.

### Builder (`cimiento.geometry.builder`)
- `build_building_from_solution(solar, program, solution) → Building`
- Espacios (un `Space` por `UnitPlacement`).
- Muros exteriores a lo largo del perímetro del solar.
- Muros interiores en límites compartidos entre unidades adyacentes.
- Una puerta por espacio (colocada en el muro adyacente de mayor longitud).
- Forjados de suelo y cubierta con el contorno del solar.
- 4 tests de contrato en `test_builder.py`.

### Exportación IFC4 (`cimiento.bim.ifc_exporter`)
- `export_to_ifc(building, output_path) → None`
- Jerarquía `IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey`.
- `IfcWallStandardCase` con geometría de extrusión (`create_2pt_wall`).
- `IfcSlab` con `PredefinedType` correcto (BASESLAB/FLOOR/ROOF).
- `IfcSpace` con volumen extruido desde el contorno en planta.
- `IfcDoor`/`IfcWindow` con posición 3D calculada desde datos del muro.
- `validate_ifc(path) → ValidationResult` para comprobación de integridad.
- 6 tests de integración en `test_ifc_export.py`.

### Exportación DXF (`cimiento.bim.dxf_exporter`)
- `export_to_dxf(building, output_path) → None`
- Capas según convención DIN 277: `MUROS_EXT`, `MUROS_INT`, `PUERTAS`,
  `VENTANAS`, `COTAS`, `TEXTOS`.
- Un bloque DXF por planta (`PLANTA_0`, `PLANTA_1`, …).
- Arcos de apertura de 90° para puertas; líneas dobles para ventanas.
- Etiquetas de espacio con `room_type` y área neta.
- 4 tests de integración en `test_exports.py`.

### Exportación XLSX (`cimiento.bim.xlsx_reporter`)
- `export_to_xlsx(building, program, output_path) → None`
- 4 hojas: Resumen, Unidades, Superficies por tipo, Parámetros urbanísticos.
- Headers en negrita con relleno azul, bordes de celda, formatos numéricos.
- 4 tests de integración en `test_exports.py`.

### Script unificado `export_all.py`
Pipeline completo en una sola llamada:
```
uv run python scripts/export_all.py data/solares_ejemplo/rectangular_simple.yaml
```

---

## Benchmark Fase 2 (solver + builder + IFC)

```
Caso                         Status       Unids   Solver  Builder     IFC    Total
5 T2 · solar 20×30 m         OPTIMAL          5   0.011s   0.000s  0.060s   0.071s
20 T2 · solar 40×60 m        OPTIMAL         20   0.009s   0.001s  0.153s   0.163s
50 T2 · solar 60×100 m       OPTIMAL         50   0.026s   0.002s  0.339s   0.367s
```

El cuello de botella es la serialización IFC de IfcOpenShell (~0.3-0.4 s para 50 unidades),
no el solver ni el builder.

---

## Cómo verificar los outputs manualmente

### IFC — BlenderBIM (recomendado)
1. Instalar Blender (gratuito) + addon BlenderBIM desde [blenderbim.org](https://blenderbim.org).
2. `Archivo → Importar → IFC` y seleccionar `data/outputs/rectangular_simple.ifc`.
3. Se visualizan los muros, forjados, espacios y puertas en 3D real con hierarchy panel.

### DXF — LibreCAD
1. `Archivo → Abrir` y seleccionar `data/outputs/rectangular_simple.dxf`.
2. En el panel de capas, activar/desactivar `MUROS_EXT`, `MUROS_INT`, `PUERTAS`.

### XLSX — LibreOffice Calc
1. Abrir `data/outputs/rectangular_simple.xlsx` con LibreOffice Calc.
2. Revisar las 4 hojas; las celdas numéricas están formateadas con separador de miles.

---

## Limitaciones heredadas a Fase 3

| Limitación | Impacto | Dónde se resuelve |
|---|---|---|
| Muros solo ortogonales | Solares irregulares no se modelan bien | `geometry/` Fase 3 |
| Sin IfcOpeningElement (no boolean cut) | Las puertas no abren físicamente el muro | `bim/ifc_exporter.py` Fase 3 |
| Espacios sin RoomType detallado (todos LIVING) | XLSX no desglosa por habitación | `geometry/builder.py` Fase 3 |
| Sin núcleos de comunicación vertical | No hay escaleras ni ascensores | Fase 3 |
| Solar sin georreferenciación real | IfcSite sin coordenadas | Fase 4 (API) |
| Área construida = neta × 1.15 (estimación fija) | XLSX no es preciso | Fase 3 |
