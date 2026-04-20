import { useEffect, useState } from 'react'
import { Box, Orbit } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { StatusBadge } from '../../components/StatusBadge'

type IfcViewerPanelProps = {
  sourceUrl?: string
}

export function IfcViewerPanel({ sourceUrl }: IfcViewerPanelProps) {
  const { t } = useTranslation()
  const [viewerState, setViewerState] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false

    void import('@thatopen/components')
      .then(() => {
        if (!cancelled) {
          setViewerState('ready')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setViewerState('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel-surface rounded-[2rem] p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-[-0.03em]">{t('ifc_viewer.title')}</h2>
          <p className="max-w-2xl text-sm leading-6 text-[color:var(--color-mist)]">
            {t('ifc_viewer.description')}
          </p>
        </div>
        <StatusBadge
          tone={viewerState === 'ready' ? 'good' : viewerState === 'error' ? 'warn' : 'neutral'}
        >
          {viewerState === 'ready'
            ? t('ifc_viewer.ready')
            : viewerState === 'error'
              ? t('ifc_viewer.library_error')
              : t('common.loading')}
        </StatusBadge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="grid-paper flex aspect-[16/10] items-center justify-center rounded-[1.75rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)]">
          <div className="space-y-3 text-center">
            <Orbit className="mx-auto text-[color:var(--color-teal)]" size={42} />
            <p className="max-w-md text-sm leading-6 text-[color:var(--color-mist)]">
              {t('ifc_viewer.placeholder')}
            </p>
          </div>
        </div>

        <div className="space-y-3 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-[color:var(--color-clay-soft)] p-3 text-[color:var(--color-clay)]">
              <Box size={20} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t('ifc_viewer.linked_file')}
              </p>
              <p className="mt-1 text-sm font-medium text-[color:var(--color-ink)]">
                {sourceUrl ?? t('ifc_viewer.not_loaded')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}