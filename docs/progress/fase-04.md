# Fase 4 — API y visualización web

**Estado:** Completada  
**Fecha:** 2026-04-20

---

## Qué se logró

### API operativa de extremo a extremo

La capa web ya expone un flujo funcional sin depender todavía de agentes LLM:

- `POST /api/projects` crea un proyecto con snapshot inicial de solar y programa.
- `GET /api/projects` y `GET /api/projects/{project_id}` permiten listar y abrir proyectos.
- `PUT /api/projects/{project_id}` crea nuevas versiones lógicas del proyecto.
- `POST /api/projects/{project_id}/generate` lanza un job de generación.
- `GET /api/jobs/{job_id}` devuelve el estado acumulado del job.
- `WS /api/jobs/{job_id}/stream` emite progreso en vivo para Solver, BIM-Aufbau y Export.
- `GET /api/projects/{project_id}/outputs/{output_format}` sirve IFC, DXF, XLSX y SVG.
- `GET /api/health` verifica el estado observable del sistema.

La persistencia ya funciona con PostgreSQL en despliegue y también puede levantarse con SQLite en desarrollo si se necesita un entorno ligero.

### Interfaz web usable en alemán

El frontend React + TypeScript entrega ya una experiencia completa para usuario final:

- Landing page y listado de proyectos.
- Creación de proyectos con seed inicial consistente.
- Edición del proyecto en `/projekte/:id`.
- Flujo de generación con botón “Entwurf generieren”.
- Feedback de errores y estados en alemán.
- Descarga de outputs desde la propia UI.

La interfaz deja de ser una demo aislada y pasa a ser el cliente principal del producto.

### Visor IFC integrado

El visor del tab `Modell` resuelve el caso BIM básico que la fase exigía:

- Carga de IFC en navegador con `@thatopen/components`.
- Árbol espacial IFC con foco por Geschoss para modelos grandes.
- Selección de elementos y panel de propiedades IFC.
- Controles de cámara y cambio de proyección.
- Corte por planta desde la UI.
- Descarga directa de IFC, DXF y XLSX asociados a la versión.

### Generación en vivo sin LLM

El sistema ya recorre el pipeline útil del producto sin inteligencia conversacional encima:

1. Crear proyecto.
2. Definir solar y programa.
3. Lanzar generación.
4. Seguir progreso por WebSocket.
5. Descargar outputs.
6. Abrir el modelo IFC dentro de la propia aplicación.

Esto confirma que el núcleo de producto es viable antes de añadir la capa conversacional de Fase 5.

### Despliegue local con Docker Compose

`infra/docker/docker-compose.yml` ya incluye el producto web completo:

- `postgres` para persistencia.
- `backend` para API y generación.
- `frontend` para servir la SPA y hacer proxy hacia la API.

`ollama` y `qdrant` quedan disponibles bajo el perfil opcional `ai`, porque no son necesarios para el flujo usable de Fase 4.

---

## Validación del hito

- Build de frontend pasando.
- Lint de los archivos modificados del flujo de generación pasando.
- Generación y descarga disponibles desde la UI.
- Visor IFC integrado en la ruta activa de proyecto.
- README actualizado con capturas de la interfaz real.

---

## Limitaciones conocidas al cerrar Fase 4

- No existe todavía interacción conversacional; todo el flujo es explícito y dirigido por formularios y acciones UI.
- La validación normativa contextual y el RAG siguen fuera del alcance de esta fase.
- La ingesta visual de planos y el render fotorrealista quedan para fases posteriores.
- El visor IFC ya es usable, pero el tratamiento de modelos muy grandes sigue siendo un área de optimización continua.

---

## Qué habilita Fase 5

La siguiente fase ya no tiene que construir el producto base; tiene que superponer inteligencia encima de un flujo probado:

- Agentes para extracción y validación de intención.
- Tool-calling validado hacia solver y servicios existentes.
- UX conversacional apoyada en proyectos, versiones, outputs y visor ya implementados.