import type { RefObject } from 'react'
import { MousePointer2, RotateCcw, ScanSearch } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export type ViewerStatus = 'loading' | 'ready' | 'error'
export type ProjectionMode = 'Perspective' | 'Orthographic'

type IfcViewerProps = {
  containerRef: RefObject<HTMLDivElement | null>
  projection: ProjectionMode
  viewerStatus: ViewerStatus
  onFit: () => void
  onProjectionChange: (projection: ProjectionMode) => void
}

export function IfcViewer({
  containerRef,
  projection,
  viewerStatus,
  onFit,
  onProjectionChange,
}: IfcViewerProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
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
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t('ifc_viewer.controls.projection')}
            </p>
            <button
              type="button"
              onClick={onFit}
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white px-3 py-2 text-sm font-semibold text-[color:var(--color-ink)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
            >
              <RotateCcw size={14} />
              {t('ifc_viewer.controls.fit')}
            </button>
          </div>

          <div className="mt-3 flex gap-2">
            {(['Perspective', 'Orthographic'] as const).map((projectionMode) => (
              <button
                key={projectionMode}
                type="button"
                onClick={() => onProjectionChange(projectionMode)}
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
  )
}