import { Activity, Play, Workflow } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { StatusBadge } from '../../components/StatusBadge'
import { formatDate } from '../../utils/format'
import type { JobEvent } from '../../types/project'

type GenerationStatusPanelProps = {
  jobId: string | null
  status: string
  events: JobEvent[]
  isPending: boolean
  onGenerate: () => void
}

function toneForStatus(status: string): 'neutral' | 'good' | 'warn' | 'accent' {
  if (status === 'finished') {
    return 'good'
  }
  if (status === 'failed') {
    return 'warn'
  }
  if (status === 'running' || status === 'queued') {
    return 'accent'
  }
  return 'neutral'
}

export function GenerationStatusPanel({
  jobId,
  status,
  events,
  isPending,
  onGenerate,
}: GenerationStatusPanelProps) {
  const { t } = useTranslation()
  const statusLabels: Record<string, string> = {
    idle: t('generation.idle'),
    queued: t('generation.queued'),
    running: t('generation.running'),
    finished: t('generation.finished'),
    failed: t('generation.failed'),
  }

  const eventLabels: Record<string, string> = {
    solver_started: t('generation.solver_started'),
    solver_progress: t('generation.solver_progress'),
    solver_finished: t('generation.solver_finished'),
    builder_started: t('generation.builder_started'),
    export_started: t('generation.export_started'),
    finished: t('generation.finished'),
    failed: t('generation.failed'),
  }

  return (
    <section className="panel-surface rounded-[2rem] p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-[-0.03em]">{t('generation.title')}</h2>
          <p className="max-w-2xl text-sm leading-6 text-[color:var(--color-mist)]">
            {t('generation.description')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={toneForStatus(status)}>
            {statusLabels[status] ?? t('generation.idle')}
          </StatusBadge>
          <button
            type="button"
            onClick={onGenerate}
            disabled={isPending}
            className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-teal)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#0c655e] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Play size={16} />
            {t('generation.start')}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <div className="space-y-3 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-[color:var(--color-clay-soft)] p-3 text-[color:var(--color-clay)]">
              <Workflow size={18} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t('generation.job')}
              </p>
              <p className="mt-1 break-all text-sm font-medium text-[color:var(--color-ink)]">
                {jobId ?? 'Noch nicht gestartet'}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
            <Activity size={16} />
            {t('generation.events')}
          </div>

          <div className="space-y-3">
            {events.length === 0 ? (
              <p className="text-sm text-[color:var(--color-mist)]">Noch keine Ereignisse vorhanden.</p>
            ) : (
              events.map((event) => (
                <div
                  key={`${event.timestamp}-${event.event}`}
                  className="rounded-2xl border border-[color:var(--color-line)] px-4 py-3"
                >
                  <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                    <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                      {eventLabels[event.event] ?? event.event}
                    </p>
                    <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--color-mist)]">
                      {formatDate(event.timestamp)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  )
}