import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ChangeEvent } from "react";
import {
  Box,
  ChevronLeft,
  ChevronRight,
  Download,
  Layers3,
  SquareStack,
} from "lucide-react";
import { useTranslation } from "react-i18next";
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
import { buildOutputUrl } from "../../api/projects";
import { StatusBadge } from "../../components/StatusBadge";
import type { GeneratedOutput, ProjectDetail } from "../../types/project";
import { IfcViewer, type ProjectionMode, type ViewerStatus } from "./IfcViewer";

const FULL_TREE_SCOPE = "full";
const STOREYS_PER_PAGE = 4;
const LARGE_TREE_THRESHOLD = 220;

type IfcTreeNode = {
  key: string;
  localId: number | null;
  category: string | null;
  modelId: string;
  children: IfcTreeNode[];
};

type ViewerSelection = {
  modelId: string;
  localId: number;
  category: string | null;
  label: string;
  properties: Array<{ key: string; value: string }>;
};

type ViewerRuntime = {
  dispose: () => void;
  fit: () => Promise<void>;
  select: (modelId: string, localId: number) => Promise<void>;
  setProjection: (projection: ProjectionMode) => Promise<void>;
  setSectionFloor: (floor: number | null) => Promise<void>;
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

function collectInitialExpanded(tree: IfcTreeNode): Record<string, boolean> {
  const expanded: Record<string, boolean> = { [tree.key]: true };
  for (const child of tree.children.slice(0, 3)) {
    expanded[child.key] = true;
  }
  return expanded;
}

function categoryKey(category: string | null): string {
  return category?.toUpperCase() ?? "unknown";
}

function countTreeNodes(node: IfcTreeNode): number {
  return (
    1 + node.children.reduce((total, child) => total + countTreeNodes(child), 0)
  );
}

function collectStoreyNodes(
  node: IfcTreeNode,
  collection: IfcTreeNode[] = [],
): IfcTreeNode[] {
  if (categoryKey(node.category) === "IFCBUILDINGSTOREY") {
    collection.push(node);
  }

  for (const child of node.children) {
    collectStoreyNodes(child, collection);
  }

  return collection;
}

function findNodeByKey(node: IfcTreeNode, key: string): IfcTreeNode | null {
  if (node.key === key) {
    return node;
  }

  for (const child of node.children) {
    const match = findNodeByKey(child, key);
    if (match) {
      return match;
    }
  }

  return null;
}

function chunkItems<T>(items: T[], size: number): T[][] {
  if (items.length === 0) {
    return [];
  }

  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }

  return chunks;
}

function sortDownloads(outputs: GeneratedOutput[]): GeneratedOutput[] {
  const preferredOrder = ["IFC", "DXF", "XLSX"];
  return preferredOrder.flatMap((outputType) =>
    outputs.filter((entry) => entry.output_type === outputType),
  );
}

function formatTreeNodeLabel(
  node: IfcTreeNode,
  t: ReturnType<typeof useTranslation>["t"],
  storeyIndexByKey: Map<string, number>,
): string {
  if (node.localId === null) {
    return t("ifc_viewer.tree.root");
  }

  if (categoryKey(node.category) === "IFCBUILDINGSTOREY") {
    const storeyIndex = storeyIndexByKey.get(node.key);
    if (typeof storeyIndex === "number") {
      return t("ifc_viewer.section.floor", { index: storeyIndex + 1 });
    }
  }

  return `${t(`ifc_viewer.categories.${categoryKey(node.category)}`)} #${node.localId}`;
}

type TreeNodeViewProps = {
  expanded: Record<string, boolean>;
  node: IfcTreeNode;
  onSelect: (node: IfcTreeNode) => void;
  onToggle: (key: string) => void;
  selectedLocalId: number | null;
  storeyIndexByKey: Map<string, number>;
};

function TreeNodeView({
  expanded,
  node,
  onSelect,
  onToggle,
  selectedLocalId,
  storeyIndexByKey,
}: TreeNodeViewProps) {
  const { t } = useTranslation();
  const hasChildren = node.children.length > 0;
  const isExpanded = Boolean(expanded[node.key]);
  const isSelected = node.localId !== null && selectedLocalId === node.localId;
  const label = formatTreeNodeLabel(node, t, storeyIndexByKey);

  return (
    <li>
      <div className="flex items-center gap-2">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggle(node.key)}
            className="rounded-full border border-[color:var(--color-line)] px-2 py-0.5 text-xs font-semibold text-[color:var(--color-mist)]"
          >
            {isExpanded ? "−" : "+"}
          </button>
        ) : (
          <span className="inline-flex h-6 w-6 items-center justify-center text-[color:var(--color-mist)]">
            •
          </span>
        )}

        <button
          type="button"
          onClick={() => onSelect(node)}
          className={[
            "rounded-xl px-3 py-2 text-left text-sm transition",
            isSelected
              ? "bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
              : "text-[color:var(--color-ink)] hover:bg-white/70",
          ].join(" ")}
        >
          {label}
        </button>
      </div>

      {hasChildren && isExpanded ? (
        <ul className="mt-2 space-y-2 border-l border-[color:var(--color-line)] pl-4">
          {node.children.map((child) => (
            <TreeNodeView
              key={child.key}
              expanded={expanded}
              node={child}
              onSelect={onSelect}
              onToggle={onToggle}
              selectedLocalId={selectedLocalId}
              storeyIndexByKey={storeyIndexByKey}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

type IfcModelWorkspaceProps = {
  outputs: GeneratedOutput[];
  project: ProjectDetail;
};

export function IfcModelWorkspace({
  outputs,
  project,
}: IfcModelWorkspaceProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const runtimeRef = useRef<ViewerRuntime | null>(null);
  const [viewerStatus, setViewerStatus] = useState<ViewerStatus>("loading");
  const [tree, setTree] = useState<IfcTreeNode | null>(null);
  const deferredTree = useDeferredValue(tree);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>(
    {},
  );
  const [selection, setSelection] = useState<ViewerSelection | null>(null);
  const [projection, setProjection] = useState<ProjectionMode>("Perspective");
  const [sectionFloor, setSectionFloor] = useState<number | null>(null);
  const [storeyPage, setStoreyPage] = useState(0);
  const [treeScope, setTreeScope] = useState<string>(FULL_TREE_SCOPE);

  const ifcOutput = outputs.find((entry) => entry.output_type === "IFC");
  const availableDownloads = useMemo(() => sortDownloads(outputs), [outputs]);
  const sourceUrl = ifcOutput ? buildOutputUrl(project.id, "ifc") : undefined;
  const floorOptions = Array.from(
    { length: project.current_version?.program.num_floors ?? 0 },
    (_, index) => index,
  );
  const floorHeight = project.current_version?.program.floor_height_m ?? 3;

  const storeyNodes = useMemo(
    () => (deferredTree ? collectStoreyNodes(deferredTree) : []),
    [deferredTree],
  );
  const storeyPages = useMemo(
    () => chunkItems(storeyNodes, STOREYS_PER_PAGE),
    [storeyNodes],
  );
  const totalTreeNodes = useMemo(
    () => (deferredTree ? countTreeNodes(deferredTree) : 0),
    [deferredTree],
  );
  const needsStoreyPagination =
    totalTreeNodes > LARGE_TREE_THRESHOLD ||
    storeyNodes.length > STOREYS_PER_PAGE;
  const activeStoreyPage = useMemo(
    () => storeyPages[storeyPage] ?? [],
    [storeyPage, storeyPages],
  );
  const storeyIndexByKey = useMemo(
    () => new Map(storeyNodes.map((node, index) => [node.key, index])),
    [storeyNodes],
  );
  const selectedStoreyKey = treeScope === FULL_TREE_SCOPE ? null : treeScope;
  const visibleTreeRoots = useMemo(() => {
    if (!deferredTree) {
      return [];
    }

    if (!selectedStoreyKey) {
      return [deferredTree];
    }

    const focusedNode = findNodeByKey(deferredTree, selectedStoreyKey);
    return focusedNode ? [focusedNode] : [deferredTree];
  }, [deferredTree, selectedStoreyKey]);

  const downloadLabels = useMemo(
    () => ({
      IFC: t("ifc_viewer.downloads.ifc"),
      DXF: t("ifc_viewer.downloads.dxf"),
      XLSX: t("ifc_viewer.downloads.xlsx"),
    }),
    [t],
  );

  useEffect(() => {
    if (!runtimeRef.current) {
      return;
    }

    void runtimeRef.current.setProjection(projection);
  }, [projection]);

  useEffect(() => {
    if (!runtimeRef.current) {
      return;
    }

    void runtimeRef.current.setSectionFloor(sectionFloor);
  }, [sectionFloor]);

  useEffect(() => {
    if (!sourceUrl || !containerRef.current) {
      return undefined;
    }

    let cancelled = false;

    const initializeViewer = async () => {
      try {
        const container = containerRef.current;
        if (!container) {
          return;
        }

        setViewerStatus("loading");
        setSelection(null);
        setTree(null);
        setExpandedNodes({});
        setTreeScope(FULL_TREE_SCOPE);
        setStoreyPage(0);
        setSectionFloor(null);
        setProjection("Perspective");

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
        const model = await ifcLoader.load(
          binary,
          true,
          `project-${project.id}`,
          {
            instanceCallback: (importer) => {
              importer.addAllAttributes();
              importer.addAllRelations();
            },
          },
        );

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
            setSelection(null);
            return;
          }

          const rawCategory =
            !Array.isArray(data.type) && data.type?.value
              ? String(data.type.value)
              : null;
          setSelection({
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
            setSelection(null);
            return;
          }

          await selectItem(result.fragments.modelId, result.localId);
        };

        canvas.addEventListener("click", handleCanvasClick);

        const spatialStructure = await model.getSpatialStructure();
        if (cancelled) {
          canvas.removeEventListener("click", handleCanvasClick);
          await model.dispose();
          components.dispose();
          return;
        }

        const mappedTree = mapSpatialTree(spatialStructure, model.modelId);
        const initialExpandedNodes = collectInitialExpanded(mappedTree);
        const initialStoreys = collectStoreyNodes(mappedTree);
        const shouldFocusStorey =
          countTreeNodes(mappedTree) > LARGE_TREE_THRESHOLD ||
          initialStoreys.length > STOREYS_PER_PAGE;
        const initialTreeScope =
          shouldFocusStorey && initialStoreys[0]
            ? initialStoreys[0].key
            : FULL_TREE_SCOPE;
        const initialSectionFloor = shouldFocusStorey ? 0 : null;

        startTransition(() => {
          setTree(mappedTree);
          setExpandedNodes(initialExpandedNodes);
          setStoreyPage(0);
          setTreeScope(initialTreeScope);
          setSectionFloor(initialSectionFloor);
          setViewerStatus("ready");
        });

        runtimeRef.current = {
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
        };
      } catch {
        if (!cancelled) {
          setViewerStatus("error");
        }
      }
    };

    void initializeViewer();

    return () => {
      cancelled = true;
      runtimeRef.current?.dispose();
      runtimeRef.current = null;
    };
  }, [floorHeight, project.current_version?.id, project.id, sourceUrl, t]);

  const handleSectionChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextValue =
      event.target.value === "all" ? null : Number(event.target.value);
    setSectionFloor(nextValue);

    if (nextValue === null) {
      setTreeScope(FULL_TREE_SCOPE);
      return;
    }

    const nextStorey = storeyNodes[nextValue];
    if (!nextStorey) {
      return;
    }

    setStoreyPage(Math.floor(nextValue / STOREYS_PER_PAGE));
    setTreeScope(nextStorey.key);
  };

  const focusStorey = (storeyKey: string) => {
    const storeyIndex = storeyIndexByKey.get(storeyKey);
    setTreeScope(storeyKey);
    setSectionFloor(typeof storeyIndex === "number" ? storeyIndex : null);
  };

  const changeStoreyPage = (nextPage: number) => {
    const maxPage = Math.max(storeyPages.length - 1, 0);
    const clampedPage = Math.max(0, Math.min(maxPage, nextPage));
    const nextPageStoreys = storeyPages[clampedPage] ?? [];

    setStoreyPage(clampedPage);

    if (treeScope === FULL_TREE_SCOPE) {
      return;
    }

    const retainedStorey = nextPageStoreys.find(
      (node) => node.key === treeScope,
    );
    const fallbackStorey = retainedStorey ?? nextPageStoreys[0];
    if (fallbackStorey) {
      focusStorey(fallbackStorey.key);
    }
  };

  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <div className="flex flex-col gap-4 border-b border-[color:var(--color-line)] pb-5">
        <div className="space-y-2">
          <StatusBadge tone="accent">
            {t("project_editor.tabs.model")}
          </StatusBadge>
          <div>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t("ifc_viewer.title")}
            </h2>
            <p className="max-w-3xl text-sm leading-7 text-[color:var(--color-mist)]">
              {t("ifc_viewer.description")}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <aside className="space-y-4 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Layers3 size={16} />
              {t("ifc_viewer.tree.title")}
            </div>
            <p className="mt-2 text-xs leading-6 text-[color:var(--color-mist)]">
              {needsStoreyPagination
                ? t("ifc_viewer.tree.performance_hint")
                : t("ifc_viewer.tree.description")}
            </p>
            {totalTreeNodes > 0 ? (
              <p className="mt-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t("ifc_viewer.tree.node_count", { count: totalTreeNodes })}
              </p>
            ) : null}
          </div>

          {needsStoreyPagination && storeyPages.length > 0 ? (
            <div className="space-y-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("ifc_viewer.storeys.title")}
                </p>
                <p className="text-xs text-[color:var(--color-mist)]">
                  {t("ifc_viewer.storeys.page", {
                    current: Math.min(storeyPage + 1, storeyPages.length),
                    total: storeyPages.length,
                  })}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => changeStoreyPage(storeyPage - 1)}
                  disabled={storeyPage === 0}
                  aria-label={t("ifc_viewer.storeys.previous_page")}
                  className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronLeft size={14} />
                </button>

                <div className="flex flex-1 flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setTreeScope(FULL_TREE_SCOPE);
                      setSectionFloor(null);
                    }}
                    className={[
                      "rounded-full border px-3 py-2 text-xs font-semibold transition",
                      treeScope === FULL_TREE_SCOPE
                        ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                        : "border-[color:var(--color-line)] bg-white text-[color:var(--color-mist)]",
                    ].join(" ")}
                  >
                    {t("ifc_viewer.storeys.all_model")}
                  </button>

                  {activeStoreyPage.map((storeyNode) => {
                    const storeyIndex =
                      storeyIndexByKey.get(storeyNode.key) ?? 0;

                    return (
                      <button
                        key={storeyNode.key}
                        type="button"
                        onClick={() => focusStorey(storeyNode.key)}
                        className={[
                          "rounded-full border px-3 py-2 text-xs font-semibold transition",
                          treeScope === storeyNode.key
                            ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                            : "border-[color:var(--color-line)] bg-white text-[color:var(--color-mist)]",
                        ].join(" ")}
                      >
                        {t("ifc_viewer.section.floor", {
                          index: storeyIndex + 1,
                        })}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  onClick={() => changeStoreyPage(storeyPage + 1)}
                  disabled={storeyPage >= storeyPages.length - 1}
                  aria-label={t("ifc_viewer.storeys.next_page")}
                  className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          ) : null}

          {visibleTreeRoots.length > 0 ? (
            <ul className="space-y-3">
              {visibleTreeRoots.map((rootNode) => (
                <TreeNodeView
                  key={rootNode.key}
                  expanded={expandedNodes}
                  node={rootNode}
                  onSelect={(node) => {
                    if (node.localId !== null) {
                      void runtimeRef.current?.select(
                        node.modelId,
                        node.localId,
                      );
                    }
                  }}
                  onToggle={(key) =>
                    setExpandedNodes((current) => ({
                      ...current,
                      [key]: !current[key],
                    }))
                  }
                  selectedLocalId={selection?.localId ?? null}
                  storeyIndexByKey={storeyIndexByKey}
                />
              ))}
            </ul>
          ) : viewerStatus === "loading" ? (
            <p className="text-sm text-[color:var(--color-mist)]">
              {t("ifc_viewer.loading")}
            </p>
          ) : (
            <p className="text-sm text-[color:var(--color-mist)]">
              {t("ifc_viewer.tree.empty")}
            </p>
          )}
        </aside>

        <IfcViewer
          containerRef={containerRef}
          projection={projection}
          viewerStatus={viewerStatus}
          onFit={() => {
            void runtimeRef.current?.fit();
          }}
          onProjectionChange={setProjection}
        />

        <aside className="space-y-4 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <SquareStack size={16} />
              {t("ifc_viewer.section.title")}
            </div>
            <select
              value={sectionFloor === null ? "all" : String(sectionFloor)}
              onChange={(event) => {
                void handleSectionChange(event);
              }}
              className="mt-3 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]"
            >
              <option value="all">{t("ifc_viewer.section.all")}</option>
              {floorOptions.map((floor) => (
                <option key={floor} value={floor}>
                  {t("ifc_viewer.section.floor", { index: floor + 1 })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Box size={16} />
              {t("ifc_viewer.properties.title")}
            </div>

            {selection ? (
              <div className="mt-3 space-y-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                    {selection.label}
                  </p>
                  <p className="mt-1 text-xs text-[color:var(--color-mist)]">
                    {t("ifc_viewer.properties.type")}:{" "}
                    {t(
                      `ifc_viewer.categories.${categoryKey(selection.category)}`,
                    )}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t("ifc_viewer.properties.local_id")}: {selection.localId}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t("ifc_viewer.properties.attribute_count", {
                      count: selection.properties.length,
                    })}
                  </p>
                </div>
                <div className="max-h-[280px] space-y-2 overflow-y-auto">
                  {selection.properties.map((property) => (
                    <div
                      key={`${property.key}-${property.value}`}
                      className="rounded-xl border border-[color:var(--color-line)] bg-white/80 px-3 py-2"
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[color:var(--color-mist)]">
                        {property.key}
                      </p>
                      <p className="mt-1 text-sm text-[color:var(--color-ink)]">
                        {property.value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-[color:var(--color-mist)]">
                {t("ifc_viewer.properties.empty")}
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Download size={16} />
              {t("ifc_viewer.downloads.title")}
            </div>
            <div className="mt-3 flex flex-col gap-2">
              {availableDownloads.map((output) => (
                <a
                  key={output.id}
                  href={buildOutputUrl(
                    project.id,
                    output.output_type.toLowerCase() as
                      | "ifc"
                      | "dxf"
                      | "xlsx"
                      | "svg",
                  )}
                  className="inline-flex items-center justify-between rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm font-semibold text-[color:var(--color-ink)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
                >
                  <span>
                    {
                      downloadLabels[
                        output.output_type as keyof typeof downloadLabels
                      ]
                    }
                  </span>
                  <Download size={15} />
                </a>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
