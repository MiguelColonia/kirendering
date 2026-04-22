import * as THREE from "three";
import * as OBC from "@thatopen/components";
import {
  RenderedFaces,
  type ItemData,
  type MaterialDefinition,
  type RaycastResult,
  type SpatialTreeItem,
} from "@thatopen/fragments";
import fragmentsWorkerUrl from "@thatopen/fragments/worker?url";
import webIfcWasmUrl from "web-ifc/web-ifc.wasm?url";
import type { ProjectionMode } from "./IfcViewer";

export type IfcTreeNode = {
  key: string;
  localId: number | null;
  category: string | null;
  modelId: string;
  children: IfcTreeNode[];
};

export type ViewerSelection = {
  modelId: string;
  localId: number;
  category: string | null;
  label: string;
  properties: Array<{ key: string; value: string }>;
};

export type ViewerRuntime = {
  dispose: () => void;
  fit: () => Promise<void>;
  select: (modelId: string, localId: number) => Promise<void>;
  setProjection: (projection: ProjectionMode) => Promise<void>;
  setSectionFloor: (floor: number | null) => Promise<void>;
};

type InitializeIfcRuntimeOptions = {
  container: HTMLDivElement;
  floorHeight: number;
  projectId: string;
  sourceUrl: string;
  t: (key: string, options?: Record<string, unknown>) => string;
  onSelectionChange: (selection: ViewerSelection | null) => void;
};

type InitializeIfcRuntimeResult = {
  runtime: ViewerRuntime;
  tree: IfcTreeNode;
};

const HIGHLIGHT_STYLE: MaterialDefinition = {
  color: new THREE.Color("#184e63"),
  renderedFaces: RenderedFaces.TWO,
  opacity: 1,
  transparent: false,
  preserveOriginalMaterial: true,
};

function isNestedItemData(value: unknown): value is ItemData {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function flattenItemData(
  data: ItemData,
  prefix = "",
): Array<{ key: string; value: string }> {
  return Object.entries(data).flatMap(([key, rawValue]) => {
    const composedKey = prefix ? `${prefix}.${key}` : key;

    if (Array.isArray(rawValue)) {
      return rawValue.flatMap((entry, index) =>
        flattenItemData(entry, `${composedKey}[${index}]`),
      );
    }

    if (isNestedItemData(rawValue) && "value" in rawValue) {
      if (
        rawValue.value === undefined ||
        rawValue.value === null ||
        rawValue.value === ""
      ) {
        return [];
      }

      return [{ key: composedKey, value: String(rawValue.value) }];
    }

    if (isNestedItemData(rawValue)) {
      return flattenItemData(rawValue, composedKey);
    }

    if (rawValue === undefined || rawValue === null) {
      return [];
    }

    const value = String(rawValue);
    if (value === "") {
      return [];
    }

    return [{ key: composedKey, value }];
  });
}

function extractLabel(data: ItemData, fallback: string): string {
  const longName = data.LongName;
  if (!Array.isArray(longName) && longName?.value) {
    return String(longName.value);
  }

  const name = data.Name;
  if (!Array.isArray(name) && name?.value) {
    return String(name.value);
  }

  const globalId = data.GlobalId;
  if (!Array.isArray(globalId) && globalId?.value) {
    return String(globalId.value);
  }

  return fallback;
}

function categoryKey(category: string | null): string {
  return category?.toUpperCase() ?? "unknown";
}

function mapSpatialTree(
  node: SpatialTreeItem,
  modelId: string,
  path = "root",
): IfcTreeNode {
  return {
    key: `${modelId}:${path}:${node.localId ?? "root"}`,
    localId: node.localId,
    category: node.category,
    modelId,
    children: (node.children ?? []).map((child, index) =>
      mapSpatialTree(child, modelId, `${path}-${index}`),
    ),
  };
}

export async function initializeIfcRuntime({
  container,
  floorHeight,
  projectId,
  sourceUrl,
  t,
  onSelectionChange,
}: InitializeIfcRuntimeOptions): Promise<InitializeIfcRuntimeResult> {
  const components = new OBC.Components();
  const worlds = components.get(OBC.Worlds);
  const world = worlds.create<
    OBC.SimpleScene,
    OBC.OrthoPerspectiveCamera,
    OBC.SimpleRenderer
  >();
  world.scene = new OBC.SimpleScene(components);
  world.scene.setup();
  world.scene.three.background = null;
  const renderer = new OBC.SimpleRenderer(components, container);
  world.renderer = renderer;
  world.camera = new OBC.OrthoPerspectiveCamera(components);
  components.init();

  const grid = components.get(OBC.Grids).create(world);
  grid.fade = false;

  const fragments = components.get(OBC.FragmentsManager);
  fragments.init(fragmentsWorkerUrl);

  const clipper = components.get(OBC.Clipper);
  clipper.setup();

  const ifcLoader = components.get(OBC.IfcLoader);
  await ifcLoader.setup({
    autoSetWasm: false,
    wasm: {
      path: webIfcWasmUrl,
      absolute: true,
    },
  });

  const response = await fetch(sourceUrl);
  if (!response.ok) {
    throw new Error("ifc-fetch-failed");
  }

  const binary = new Uint8Array(await response.arrayBuffer());
  const model = await ifcLoader.load(binary, true, `project-${projectId}`, {
    instanceCallback: (importer) => {
      importer.addAllAttributes();
      importer.addAllRelations();
    },
  });

  model.useCamera(world.camera.three);
  model.getClippingPlanesEvent = () => renderer.clippingPlanes;
  world.scene.three.add(model.object);
  world.camera.controls.addEventListener("update", () => {
    void fragments.core.update(false);
  });
  await world.camera.fitToItems();
  await fragments.core.update(true);

  const selectItem = async (modelId: string, localId: number) => {
    await fragments.resetHighlight();
    await fragments.highlight(HIGHLIGHT_STYLE, {
      [modelId]: new Set([localId]),
    });

    const [data] = await model.getItemsData([localId], {
      attributesDefault: true,
      relationsDefault: { attributes: false, relations: false },
      relations: {
        IsDefinedBy: { attributes: true, relations: false },
      },
    });

    if (!data) {
      onSelectionChange(null);
      return;
    }

    const rawCategory =
      !Array.isArray(data.type) && data.type?.value
        ? String(data.type.value)
        : null;
    onSelectionChange({
      modelId,
      localId,
      category: rawCategory,
      label: extractLabel(
        data,
        `${t(`ifc_viewer.categories.${categoryKey(rawCategory)}`)} #${localId}`,
      ),
      properties: flattenItemData(data),
    });
  };

  const applySectionFloor = async (floor: number | null) => {
    clipper.deleteAll();

    if (floor !== null) {
      const bottomHeight = floor * floorHeight;
      const topHeight = (floor + 1) * floorHeight;

      clipper.createFromNormalAndCoplanarPoint(
        world,
        new THREE.Vector3(0, 0, 1),
        new THREE.Vector3(0, 0, bottomHeight),
      );
      clipper.createFromNormalAndCoplanarPoint(
        world,
        new THREE.Vector3(0, 0, -1),
        new THREE.Vector3(0, 0, topHeight),
      );
    }

    renderer.updateClippingPlanes();
    await fragments.core.update(true);
  };

  const canvas = renderer.three.domElement;
  const handleCanvasClick = async (event: MouseEvent) => {
    const bounds = canvas.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
      -((event.clientY - bounds.top) / bounds.height) * 2 + 1,
    );

    const result = (await fragments.raycast({
      camera: world.camera.three,
      mouse,
      dom: canvas,
    })) as RaycastResult | undefined;

    if (!result) {
      await fragments.resetHighlight();
      onSelectionChange(null);
      return;
    }

    await selectItem(result.fragments.modelId, result.localId);
  };

  canvas.addEventListener("click", handleCanvasClick);

  const spatialStructure = await model.getSpatialStructure();

  return {
    tree: mapSpatialTree(spatialStructure, model.modelId),
    runtime: {
      dispose: () => {
        canvas.removeEventListener("click", handleCanvasClick);
        clipper.deleteAll();
        void model.dispose();
        components.dispose();
      },
      fit: async () => {
        await world.camera.fitToItems();
      },
      select: selectItem,
      setProjection: async (nextProjection) => {
        await world.camera.projection.set(nextProjection);
        await world.camera.fitToItems();
      },
      setSectionFloor: applySectionFloor,
    },
  };
}