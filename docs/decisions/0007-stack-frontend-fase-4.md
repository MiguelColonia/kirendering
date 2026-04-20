# ADR 0007 — Stack frontend para Fase 4

**Estado:** Aceptado  
**Fecha:** 2026-04-20  
**Contexto:** Cierre de Fase 4 con producto web usable sin copiloto de IA.

---

## Contexto

Fase 4 exigía entregar una interfaz web real para operar el sistema completo sin depender todavía de LangGraph, Ollama ni RAG. La UI tenía que cubrir al menos:

- listado y creación de proyectos,
- edición de solar y programa,
- lanzamiento de generación,
- progreso en vivo por WebSocket,
- visualización IFC en navegador,
- descarga de outputs derivados.

La decisión debía favorecer velocidad de implementación, ergonomía local, separación clara respecto a FastAPI y soporte fiable para un visor BIM en cliente.

---

## Opciones consideradas

### Opción A — SPA con React + TypeScript + Vite + router/estado explícitos (elegida)

Stack seleccionado:

- React 19 + TypeScript
- Vite
- React Router
- TanStack Query
- i18next
- Konva para edición 2D
- `@thatopen/components` + `@thatopen/fragments` + `web-ifc` para visor BIM

**Ventajas:**

- Encaja bien con un backend FastAPI independiente.
- Iteración muy rápida en local.
- Estado cliente explícito y predecible para jobs y WebSocket.
- Permite construir un visor IFC avanzado sin SSR ni acoplamiento al servidor.
- Facilita internacionalización desde el primer día.

**Desventajas:**

- Obliga a resolver manualmente routing, fetch y sincronización de estado.
- Añade trabajo explícito de proxy/despliegue para el mismo origen en producción local.
- El visor IFC depende de una librería especializada y pesada en cliente.

### Opción B — Framework full-stack con SSR/acciones de servidor

Ejemplos: Next.js o Remix.

**Ventajas:**

- Convenciones integradas para routing, fetch y despliegue.
- Buen punto de partida si el producto fuera principalmente contenido o formularios.

**Desventajas:**

- Añade complejidad innecesaria para una app local centrada en visualización BIM y jobs WebSocket.
- No aporta ventaja clara para el visor IFC, que sigue siendo intensivo en cliente.
- Introduce más superficie de integración con FastAPI o incentiva mezclar responsabilidades.

### Opción C — UI mínima ad hoc con visor raw y estado manual

SPA ligera con menos librerías, usando un visor IFC más básico o integraciones directas de bajo nivel.

**Ventajas:**

- Menos dependencias iniciales.
- Curva conceptual aparentemente menor.

**Desventajas:**

- Más coste de implementación para árbol IFC, propiedades, selección y recorte.
- Riesgo alto de rehacer piezas de infraestructura de frontend más adelante.
- Menor calidad de producto en un hito que ya debía ser usable.

---

## Decisión

Se adopta la **Opción A**: una SPA local con **React + TypeScript + Vite**, estado de servidor con **TanStack Query**, i18n con **i18next**, edición 2D con **Konva** y visor BIM con **That Open Components** sobre `web-ifc`.

La razón principal es pragmática: es el stack que mejor equilibra velocidad de entrega, control del cliente, integración con FastAPI y madurez suficiente para el visor IFC que Fase 4 necesitaba.

---

## Consecuencias

- El frontend queda desacoplado del backend y puede desplegarse como servicio separado.
- La app funciona bien en desarrollo y también detrás de un proxy web de mismo origen.
- La base para Fase 5 ya existe: la capa conversacional podrá montarse sobre páginas, jobs y visores reales.
- Se acepta como deuda la necesidad de mantener dependencias especializadas de visualización BIM y optimizar bundle/rendimiento cuando los modelos crezcan.

---

## Revisión

Revisar esta ADR si ocurre alguna de estas condiciones:

- Fase 5 exige SSR real o rendering híbrido con ventaja clara sobre la SPA actual.
- El visor IFC actual no escala de forma suficiente para los casos objetivo.
- La UX conversacional requiere otra organización del frontend que haga ineficiente la arquitectura elegida.