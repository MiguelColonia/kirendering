import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, PlayCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { buildOutputUrl, generateProject } from '../api/projects'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { GenerationStatusPanel } from '../features/generation/GenerationStatusPanel'
import { IfcViewerPanel } from '../features/ifc-viewer/IfcViewerPanel'
import { useProjectDetailQuery } from '../features/projects/useProjectsQuery'
import { useJobStream } from '../hooks/useJobStream'
import type { JobEvent } from '../types/project'
import { formatArea, formatDate, polygonArea } from '../utils/format'

const outputFormatLabels = {
  IFC: 'viewer.downloads.ifc',
  DXF: 'viewer.downloads.dxf',
  XLSX: 'viewer.downloads.xlsx',
  SVG: 'viewer.downloads.svg',
} as const

export function ProjectViewerPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { projectId } = useParams()
  const projectQuery = useProjectDetailQuery(projectId)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState('idle')
  const [events, setEvents] = useState<JobEvent[]>([])

  useEffect(() => {
    setActiveJobId(null)
    setJobStatus('idle')
    setEvents([])
  }, [projectId])

  useJobStream(activeJobId, (event) => {
    setEvents((currentEvents) => {
      const alreadyPresent = currentEvents.some(
        (item) => item.timestamp === event.timestamp && item.event === event.event,
      )
      if (alreadyPresent) {
        return currentEvents
      }

      return [...currentEvents, event]
    })

    if (event.event === 'finished') {
      setJobStatus('finished')
      void queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      return
    }

    if (event.event === 'failed') {
      setJobStatus('failed')
      return
    }

    setJobStatus('running')
  })

  const generateMutation = useMutation({
    mutationFn: async () => generateProject(projectId!),
    onSuccess: ({ job_id, status }) => {
      setActiveJobId(job_id)
      setJobStatus(status)
      setEvents([])
    },
  })

  if (!projectId) {
    return null
  }

  if (projectQuery.isLoading) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">{t('common.loading')}</p>
      </section>
    )
  }

  if (!projectQuery.data) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">{t('common.empty')}</p>
      </section>
    )
  }

  const currentVersion = projectQuery.data.current_version
  const outputs = currentVersion?.generated_outputs ?? []
  const ifcOutput = outputs.find((output) => output.output_type === 'IFC')
  const placedUnits = currentVersion?.solution?.metrics.num_units_placed ?? 0
  const siteArea = currentVersion ? polygonArea(currentVersion.solar.contour.points) : 0

  return (
    <div className="space-y-6">
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <PageHeader
          eyebrow={t('viewer.current_version')}
          title={projectQuery.data.name}
          description={projectQuery.data.description || t('viewer.summary')}
          actions={
            <button
              type="button"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-clay)] px-5 py-3 text-sm font-semibold text-white"
            >
              <PlayCircle size={16} />
              {t('generation.start')}
            </button>
          }
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]">
        <section className="panel-surface rounded-[2rem] p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-[-0.03em]">{t('viewer.summary')}</h2>
            <StatusBadge tone="accent">
              {t('viewer.current_version')}: {currentVersion?.version_number ?? 0}
            </StatusBadge>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                Grundstück
              </p>
              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{formatArea(siteArea)}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                Wohneinheiten platziert
              </p>
              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{placedUnits}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                Geschosse
              </p>
              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{currentVersion?.program.num_floors ?? 0}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                Zuletzt geändert
              </p>
              <p className="mt-2 text-sm font-medium text-[color:var(--color-ink)]">
                {formatDate(projectQuery.data.updated_at)}
              </p>
            </div>
          </div>
        </section>

        <GenerationStatusPanel
          jobId={activeJobId}
          status={generateMutation.isPending ? 'queued' : jobStatus}
          events={events}
          isPending={generateMutation.isPending}
          onGenerate={() => generateMutation.mutate()}
        />
      </div>

      <IfcViewerPanel sourceUrl={ifcOutput ? buildOutputUrl(projectId, 'ifc') : undefined} />

      <section className="panel-surface rounded-[2rem] p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold tracking-[-0.03em]">{t('viewer.outputs')}</h2>
          <StatusBadge>{outputs.length} Dateien</StatusBadge>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          {outputs.length === 0 ? (
            <p className="text-sm text-[color:var(--color-mist)]">{t('viewer.no_outputs')}</p>
          ) : (
            outputs.map((output) => (
              <a
                key={output.id}
                href={buildOutputUrl(projectId, output.output_type.toLowerCase() as 'ifc' | 'dxf' | 'xlsx' | 'svg')}
                className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-4 py-3 text-sm font-medium"
              >
                <Download size={16} />
                {t(outputFormatLabels[output.output_type as keyof typeof outputFormatLabels])}
              </a>
            ))
          )}
        </div>
      </section>
    </div>
  )
}