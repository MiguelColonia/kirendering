# Arquitectura de Cimiento

## Principio fundamental

Separación estricta en tres niveles de inteligencia:

1. **Razonamiento** (LLM): conversa, orquesta, explica. NO decide geometría.
2. **Optimización** (OR-Tools): resuelve distribución espacial bajo restricciones. Determinista.
3. **Materialización** (IfcOpenShell + Shapely): traduce solución abstracta a BIM real.

Las capas superiores pueden invocar a las inferiores; nunca al revés. La geometría no se delega al LLM y el IFC4 sigue siendo el modelo canónico del proyecto.

## Capas operativas

1. **Solver**: CP-SAT para layout y validación de restricciones espaciales.
2. **Geometry/BIM**: operaciones geométricas puras y exportación IFC/DXF/XLSX.
3. **RAG normativo**: recuperación de normativa alemana con citas trazables.
4. **Visión**: OpenCV + VLM para interpretar planos 2D, siempre bajo revisión humana antes de afectar el solver.
5. **API y frontend**: FastAPI, WebSocket, React y visor IFC.
6. **Render y difusión**: render determinista desde IFC y variantes generativas derivadas de imágenes, sin modificar el modelo BIM fuente.

## Flujo de una petición típica

1. Usuario envía prompt en lenguaje natural.
2. LangGraph → Agente de Requisitos extrae parámetros.
3. Agente Normativo valida contra RAG normativo.
4. Agente Topológico INVOCA el solver (no resuelve él mismo).
5. OR-Tools devuelve solución o infactibilidad.
6. Agente Validador revisa; si falla, vuelve al paso 2-4.
7. Módulo BIM genera IFC/DXF/XLSX.
8. Render/difusión generan salidas visuales derivadas desde el IFC o una imagen de referencia.
9. API devuelve resultado al frontend.

## Restricciones de mantenimiento

- La salida de visión es un borrador y requiere revisión humana.
- El render y la difusión no reescriben el IFC ni alteran el modelo semántico.
- Los contratos entre capas viajan por schemas Pydantic.
