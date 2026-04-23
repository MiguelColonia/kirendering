/**
 * Estrategia de partición manual de bundles para el build de producción (Vite/Rollup).
 *
 * Por qué se parte manualmente y no se confía en el chunking automático:
 *  - `web-ifc` incluye un WASM de ~5 MB: separarlo evita bloquear la carga inicial.
 *  - `three` + `camera-controls` son dependencias del visor IFC cargadas de forma
 *    lazy; ponerlos en su propio chunk garantiza que solo se descargan cuando el
 *    usuario abre la pestaña "Modell".
 *  - `react-konva`/`konva` son dependencias del editor de solar, también lazy.
 *  - React, react-dom y react-router comparten chunk para maximizar el cache hit
 *    entre páginas (cambian poco entre releases).
 *  - `@tanstack/react-query` separa la capa de data-fetching del runtime de UI.
 *
 * Devuelve `undefined` para módulos propios (src/), que Rollup agrupa por ruta.
 */
export function manualChunkName(id: string): string | undefined {
  if (!id.includes("node_modules")) {
    return undefined;
  }

  if (id.includes("web-ifc")) {
    return "ifc-web-ifc";
  }

  if (id.includes("three") || id.includes("camera-controls")) {
    return "ifc-three";
  }

  if (id.includes("react-konva") || id.includes("/konva/")) {
    return "canvas-editor";
  }

  if (
    id.includes("/node_modules/react/") ||
    id.includes("/node_modules/react-dom/") ||
    id.includes("/node_modules/react-router/") ||
    id.includes("/node_modules/react-router-dom/")
  ) {
    return "app-react";
  }

  if (id.includes("@tanstack/react-query")) {
    return "app-query";
  }

  return undefined;
}
