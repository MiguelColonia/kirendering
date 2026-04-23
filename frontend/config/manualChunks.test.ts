import { describe, expect, it } from "vitest";
import { manualChunkName } from "./manualChunks";

describe("manualChunkName", () => {
  it("lässt That Open IFC-Pakete vom Bundler feiner aufteilen", () => {
    expect(
      manualChunkName(
        "/workspace/node_modules/@thatopen/components/dist/index.mjs",
      ),
    ).toBeUndefined();
    expect(
      manualChunkName(
        "/workspace/node_modules/@thatopen/fragments/dist/index.mjs",
      ),
    ).toBeUndefined();
  });

  it("behält dedizierte Async-Chunks für die schwersten Viewer-Abhängigkeiten", () => {
    expect(
      manualChunkName(
        "/workspace/node_modules/web-ifc/web-ifc-api.js",
      ),
    ).toBe("ifc-web-ifc");
    expect(
      manualChunkName(
        "/workspace/node_modules/three/build/three.module.js",
      ),
    ).toBe("ifc-three");
    expect(
      manualChunkName(
        "/workspace/node_modules/camera-controls/dist/camera-controls.module.js",
      ),
    ).toBe("ifc-three");
  });

  it("behält stabile Chunks für React, Query und den Canvas-Editor", () => {
    expect(
      manualChunkName("/workspace/node_modules/react/index.js"),
    ).toBe("app-react");
    expect(
      manualChunkName(
        "/workspace/node_modules/@tanstack/react-query/build/index.js",
      ),
    ).toBe("app-query");
    expect(
      manualChunkName("/workspace/node_modules/react-konva/lib/ReactKonva.js"),
    ).toBe("canvas-editor");
  });
});