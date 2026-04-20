import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Box, Download, Layers3, MousePointer2, RotateCcw, ScanSearch, SquareStack } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import * as THREE from 'three'
import * as OBC from '@thatopen/components'
import {
  RenderedFaces,
  type ItemData,
  type MaterialDefinition,
  type RaycastResult,
  type SpatialTreeItem,
} from '@thatopen/fragments'
import fragmentsWorkerUrl from '@thatopen/fragments/dist/Worker/worker.mjs?url'
import webIfcWasmUrl from 'web-ifc/web-ifc.wasm?url'
import { buildOutputUrl } from '../../api/projects'
import { StatusBadge } from '../../components/StatusBadge'
import type { GeneratedOutput, ProjectDetail } from '../../types/project'

type ViewerStatus = 'loading' | 'ready' | 'error'

type IfcTreeNode = {
  key: string
  localId: number | null
  category: string | null
  modelId: string
  children: IfcTreeNode[]
}

type ViewerSelection = {
  modelId: string
  localId: number
  label: string
  properties: Array<{ key: string; value: string }>
}

type ViewerRuntime = {
  dispose: () => void
  fit: () => Promise<void>
  select: (modelId: string, localId: number) => Promise<void>
  setProjection: (projection: 'Perspective' | 'Orthographic') => Promise<void>
  setSectionFloor: (floor: number | null) => Promise<void>
}

const HIGHLIGHT_STYLE: MaterialDefinition = {
  color: new THREE.Color('#184e63'),
  renderedFaces: RenderedFaces.TWO,
  opacity: 1,
  transparent: false,
  preserveOriginalMaterial: true,
}

function flattenItemData(data: ItemData, prefix = ''): Array<{ key: string; value: string }> {
  return Object.entries(data).flatMap(([key, rawValue]) => {
    const composedKey = prefix ? `${prefix}.${key}` : key

    if (Array.isArray(rawValue)) {
      return rawValue.flatMap((entry, index) => flattenItemData(entry, `${composedKey}[${index}]`))
    }

    if (rawValue?.value === undefined || rawValue?.value === null || rawValue?.value === '') {
      return []
    }

    return [{ key: composedKey, value: String(rawValue.value) }]
  })
}

function extractLabel(data: ItemData, fallback: string): string {
  const name = data.Name
  if (!Array.isArray(name) && name?.value) {
    return String(name.value)
  }

  const globalId = data.GlobalId
  if (!Array.isArray(globalId) && globalId?.value) {
    return String(globalId.value)
  }

  return fallback
}

function mapSpatialTree(node: SpatialTreeItem, modelId: string, path = 'root'): IfcTreeNode {
  return {
    key: `${modelId}:${path}:${node.localId ?? 'root'}`,
    localId: node.localId,
    category: node.category,
    modelId,
    children: (node.children ?? []).map((child, index) => mapSpatialTree(child, modelId, `${path}-${index}`)),
  }
}

function collectInitialExpanded(tree: IfcTreeNode): Record<string, boolean> {
  const expanded: Record<string, boolean> = { [tree.key]: true }
  for (const child of tree.children.slice(0, 2)) {
    expanded[child.key] = true
  }
  return expanded
}

function categoryKey(category: string | null): string {
  return category?.toUpperCase() ?? 'unknown'
}

type TreeNodeViewProps = {
  expanded: Record<string, boolean>
  node: IfcTreeNode
  onSelect: (node: IfcTreeNode) => void
  onToggle: (key: string) => void
  selectedLocalId: number | null
}

function TreeNodeView({ expanded, node, onSelect, onToggle, selectedLocalId }: TreeNodeViewProps) {
  const { t } = useTranslation()
  const hasChildren = node.children.length > 0
  const isExpanded = Boolean(expanded[node.key])
  const isSelected = node.localId !== null && selectedLocalId === node.localId
  const label =
    node.localId === null
      ? t('ifc_viewer.tree.root')
      : `${t(`ifc_viewer.categories.${categoryKey(node.category)}`)} #${node.localId}`

  return (
    <li>
      <div className="flex items-center gap-2">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggle(node.key)}
            className="rounded-full border border-[color:var(--color-line)] px-2 py-0.5 text-xs font-semibold text-[color:var(--color-mist)]"
          >
            {isExpanded ? '−' : '+'}
          </button>
        ) : (
          <span className="inline-flex h-6 w-6 items-center justify-center text-[color:var(--color-mist)]">•</span>
        )}

        <button
          type="button"
          onClick={() => onSelect(node)}
          className={[
            'rounded-xl px-3 py-2 text-left text-sm transition',
            isSelected
              ? 'bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]'
              : 'text-[color:var(--color-ink)] hover:bg-white/70',
          ].join(' ')}
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
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

type IfcModelWorkspaceProps = {
  outputs: GeneratedOutput[]
  project: ProjectDetail
}

export function IfcModelWorkspace({ outputs, project }: IfcModelWorkspaceProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const runtimeRef = useRef<ViewerRuntime | null>(null)
  const [viewerStatus, setViewerStatus] = useState<ViewerStatus>('loading')
  const [tree, setTree] = useState<IfcTreeNode | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({})
  const [selection, setSelection] = useState<ViewerSelection | null>(null)
  const [projection, setProjection] = useState<'Perspective' | 'Orthographic'>('Perspective')
  const [sectionFloor, setSectionFloor] = useState<number | null>(null)

  const ifcOutput = outputs.find((entry) => entry.output_type === 'IFC')
  const availableDownloads = outputs.filter((entry) => ['IFC', 'DXF', 'XLSX'].includes(entry.output_type))
  const sourceUrl = ifcOutput ? buildOutputUrl(project.id, 'ifc') : undefined
  const floorOptions = Array.from(
    { length: project.current_version?.program.num_floors ?? 0 },
    (_, index) => index,
  )

  const downloadLabels = useMemo(
    () => ({
      IFC: t('ifc_viewer.downloads.ifc'),
      DXF: t('ifc_viewer.downloads.dxf'),
      XLSX: t('ifc_viewer.downloads.xlsx'),
    }),
    [t],
  )

  useEffect(() => {
    if (!containerRef.current || !sourceUrl) {
      return undefined
    }

    let cancelled = false

    const initializeViewer = async () => {
      try {
        setViewerStatus('loading')
        setSelection(null)
        setTree(null)

        const components = new OBC.Components()
        const worlds = components.get(OBC.Worlds)
        const world = worlds.create<OBC.SimpleScene, OBC.OrthoPerspectiveCamera, OBC.SimpleRenderer>()
        world.scene = new OBC.SimpleScene(components)
        world.scene.setup()
        world.scene.three.background = null
        world.renderer = new OBC.SimpleRenderer(components, containerRef.current)
        world.camera = new OBC.OrthoPerspectiveCamera(components)
        components.init()

        const grid = components.get(OBC.Grids).create(world)
        grid.fade = false

        const fragments = components.get(OBC.FragmentsManager)
        fragments.init(fragmentsWorkerUrl)

        const clipper = components.get(OBC.Clipper)
        clipper.setup()

        const ifcLoader = components.get(OBC.IfcLoader)
        await ifcLoader.setup({
          autoSetWasm: false,
          wasm: {
            path: webIfcWasmUrl,
            absolute: true,
          },
        })

        const response = await fetch(sourceUrl)
        if (!response.ok) {
          throw new Error('ifc-fetch-failed')
        }

        const binary = new Uint8Array(await response.arrayBuffer())
        const model = await ifcLoader.load(binary, true, `project-${project.id}`, {
          instanceCallback: (importer) => {
            importer.addAllAttributes()
            importer.addAllRelations()
          },
        })

        model.useCamera(world.camera.three)
        model.getClippingPlanesEvent = () => world.renderer.clippingPlanes
        world.scene.three.add(model.object)
        world.camera.controls.addEventListener('update', () => {
          void fragments.core.update(false)
        })
        await world.camera.fitToItems()
        await fragments.core.update(true)

        const selectItem = async (modelId: string, localId: number) => {
          await fragments.resetHighlight()
          await fragments.highlight(HIGHLIGHT_STYLE, { [modelId]: [localId] })

          const [data] = await model.getItemsData([localId], {
            attributesDefault: true,
            relationsDefault: { attributes: false, relations: false },
            relations: {
              IsDefinedBy: { attributes: true, relations: false },
            },
          })

          const rawCategory = !Array.isArray(data.type) && data.type?.value ? String(data.type.value) : null
          setSelection({
            modelId,
            localId,
            label: extractLabel(
              data,
              `${t(`ifc_viewer.categories.${categoryKey(rawCategory)}`)} #${localId}`,
            ),
            properties: flattenItemData(data),
          })
        }

        const applySectionFloor = async (floor: number | null) => {
          clipper.deleteAll()
          if (floor !== null) {
            const sectionHeight = (floor + 1) * (project.current_version?.program.floor_height_m ?? 3)
            clipper.createFromNormalAndCoplanarPoint(
              world,
              new THREE.Vector3(0, 0, -1),
              new THREE.Vector3(0, 0, sectionHeight),
            )
          }
          world.renderer.updateClippingPlanes()
          await fragments.core.update(true)
        }

        const canvas = world.renderer.three.domElement
        const handleCanvasClick = async (event: MouseEvent) => {
          const bounds = canvas.getBoundingClientRect()
          const mouse = new THREE.Vector2(
            ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
            -((event.clientY - bounds.top) / bounds.height) * 2 + 1,
          )

          const result = (await fragments.raycast({
            camera: world.camera.three,
            mouse,
            dom: canvas,
          })) as RaycastResult | undefined

          if (!result) {
            await fragments.resetHighlight()
            setSelection(null)
            return
          }

          await selectItem(result.fragments.modelId, result.localId)
        }

        canvas.addEventListener('click', handleCanvasClick)

        const spatialStructure = await model.getSpatialStructure()
        if (cancelled) {
          canvas.removeEventListener('click', handleCanvasClick)
          await model.dispose()
          components.dispose()
          return
        }

        const mappedTree = mapSpatialTree(spatialStructure, model.modelId)
        setTree(mappedTree)
        setExpandedNodes(collectInitialExpanded(mappedTree))
        setViewerStatus('ready')

        runtimeRef.current = {
          dispose: () => {
            canvas.removeEventListener('click', handleCanvasClick)
            clipper.deleteAll()
            void model.dispose()
            components.dispose()
          },
          fit: async () => {
            await world.camera.fitToItems()
          },
          select: selectItem,
          setProjection: async (nextProjection) => {
            await world.camera.projection.set(nextProjection)
            await world.camera.fitToItems()
          },
          setSectionFloor: applySectionFloor,
        }
      } catch {
        if (!cancelled) {
          setViewerStatus('error')
        }
      }
    }

    void initializeViewer()

    return () => {
      cancelled = true
      runtimeRef.current?.dispose()
      runtimeRef.current = null
    }
  }, [project.current_version?.id, project.current_version?.program.floor_height_m, project.id, sourceUrl, t])

  const handleSectionChange = async (event: ChangeEvent<HTMLSelectElement>) => {
    const nextValue = event.target.value === 'all' ? null : Number(event.target.value)
    setSectionFloor(nextValue)
    await runtimeRef.current?.setSectionFloor(nextValue)
  }

  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <div className="flex flex-col gap-4 border-b border-[color:var(--color-line)] pb-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <StatusBadge tone="accent">{t('project_editor.tabs.model')}</StatusBadge>
          <div>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t('ifc_viewer.title')}
            </h2>
            <p className="max-w-3xl text-sm leading-7 text-[color:var(--color-mist)]">
              {t('ifc_viewer.description')}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => void runtimeRef.current?.fit()}
          className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/85 px-4 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
        >
          <RotateCcw size={16} />
          {t('ifc_viewer.controls.fit')}
        </button>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <aside className="space-y-4 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Layers3 size={16} />
              {t('ifc_viewer.tree.title')}
            </div>
            <p className="mt-2 text-xs leading-6 text-[color:var(--color-mist)]">
              {t('ifc_viewer.tree.description')}
            </p>
          </div>

          {tree ? (
            <ul className="space-y-3">
              <TreeNodeView
                expanded={expandedNodes}
                node={tree}
                onSelect={(node) => {
                  if (node.localId !== null) {
                    void runtimeRef.current?.select(node.modelId, node.localId)
                  }
                }}
                onToggle={(key) =>
                  setExpandedNodes((current) => ({
                    ...current,
                    [key]: !current[key],
                  }))
                }
                selectedLocalId={selection?.localId ?? null}
              />
            </ul>
          ) : viewerStatus === 'loading' ? (
            <p className="text-sm text-[color:var(--color-mist)]">{t('ifc_viewer.loading')}</p>
          ) : (
            <p className="text-sm text-[color:var(--color-mist)]">{t('ifc_viewer.tree.empty')}</p>
          )}
        </aside>

        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
                <MousePointer2 size={16} />
                {t('ifc_viewer.controls.instructions_title')}
              </div>
              <p className="mt-2 text-sm leading-6 text-[color:var(--color-mist)]">
                {t('ifc_viewer.controls.instructions')}
              </p>
            </div>

            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t('ifc_viewer.controls.projection')}
              </p>
              <div className="mt-3 flex gap-2">
                {(['Perspective', 'Orthographic'] as const).map((projectionMode) => (
                  <button
                    key={projectionMode}
                    type="button"
                    onClick={() => {
                      setProjection(projectionMode)
                      void runtimeRef.current?.setProjection(projectionMode)
                    }}
                    className={[
                      'rounded-full border px-3 py-2 text-sm font-semibold transition',
                      projection === projectionMode
                        ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]'
                        : 'border-[color:var(--color-line)] text-[color:var(--color-mist)]',
                    ].join(' ')}
                  >
                    {t(`ifc_viewer.controls.${projectionMode.toLowerCase()}`)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[1.75rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)]">
            <div ref={containerRef} className="h-[620px] w-full" />

            {viewerStatus === 'loading' ? (
              <div className="absolute inset-0 flex items-center justify-center bg-[color:var(--color-paper)]/72 backdrop-blur-sm">
                <div className="space-y-2 text-center">
                  <ScanSearch className="mx-auto text-[color:var(--color-accent)]" size={34} />
                  <p className="text-sm text-[color:var(--color-mist)]">{t('ifc_viewer.loading')}</p>
                </div>
              </div>
            ) : null}

            {viewerStatus === 'error' ? (
              <div className="absolute inset-0 flex items-center justify-center bg-[color:var(--color-paper)]/84 backdrop-blur-sm">
                <div className="max-w-md space-y-2 text-center">
                  <p className="text-base font-semibold text-[color:var(--color-ink)]">
                    {t('ifc_viewer.error')}
                  </p>
                  <p className="text-sm leading-6 text-[color:var(--color-mist)]">
                    {t('ifc_viewer.error_detail')}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <aside className="space-y-4 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <SquareStack size={16} />
              {t('ifc_viewer.section.title')}
            </div>
            <select
              value={sectionFloor === null ? 'all' : String(sectionFloor)}
              onChange={(event) => {
                void handleSectionChange(event)
              }}
              className="mt-3 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]"
            >
              <option value="all">{t('ifc_viewer.section.all')}</option>
              {floorOptions.map((floor) => (
                <option key={floor} value={floor}>
                  {t('ifc_viewer.section.floor', { index: floor + 1 })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Box size={16} />
              {t('ifc_viewer.properties.title')}
            </div>

            {selection ? (
              <div className="mt-3 space-y-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--color-ink)]">{selection.label}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t('ifc_viewer.properties.local_id')}: {selection.localId}
                  </p>
                </div>
                <div className="max-h-[280px] space-y-2 overflow-y-auto">
                  {selection.properties.map((property) => (
                    <div key={`${property.key}-${property.value}`} className="rounded-xl border border-[color:var(--color-line)] bg-white/80 px-3 py-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[color:var(--color-mist)]">
                        {property.key}
                      </p>
                      <p className="mt-1 text-sm text-[color:var(--color-ink)]">{property.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-[color:var(--color-mist)]">
                {t('ifc_viewer.properties.empty')}
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
              <Download size={16} />
              {t('ifc_viewer.downloads.title')}
            </div>
            <div className="mt-3 flex flex-col gap-2">
              {availableDownloads.map((output) => (
                <a
                  key={output.id}
                  href={buildOutputUrl(project.id, output.output_type.toLowerCase() as 'ifc' | 'dxf' | 'xlsx' | 'svg')}
                  className="inline-flex items-center justify-between rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm font-semibold text-[color:var(--color-ink)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
                >
                  <span>{downloadLabels[output.output_type as keyof typeof downloadLabels]}</span>
                  <Download size={15} />
                </a>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}