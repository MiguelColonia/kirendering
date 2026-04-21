import type { JobEvent } from '../../types/project'

export type RenderProgress = {
  percent: number
  estimatedTotalSeconds: number | null
  remainingSeconds: number | null
  startedAt: string | null
  view: string | null
}

function readNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function getRenderProgress(
  events: JobEvent[],
  status: string,
  now: number = Date.now(),
): RenderProgress {
  const startEvent = events.find((event) => event.event === 'render_started')
  const estimatedTotalSeconds = readNumber(startEvent?.data.estimated_total_seconds)
  const startedAt = startEvent?.timestamp ?? null
  const view = typeof startEvent?.data.view === 'string' ? startEvent.data.view : null

  if (status === 'finished') {
    return {
      percent: 100,
      estimatedTotalSeconds,
      remainingSeconds: 0,
      startedAt,
      view,
    }
  }

  if (!startedAt || estimatedTotalSeconds === null) {
    return {
      percent: status === 'queued' ? 4 : 0,
      estimatedTotalSeconds,
      remainingSeconds: estimatedTotalSeconds,
      startedAt,
      view,
    }
  }

  const elapsedSeconds = Math.max(0, Math.floor((now - Date.parse(startedAt)) / 1000))
  const percent = Math.min(95, Math.max(8, (elapsedSeconds / estimatedTotalSeconds) * 100))

  return {
    percent,
    estimatedTotalSeconds,
    remainingSeconds: Math.max(0, estimatedTotalSeconds - elapsedSeconds),
    startedAt,
    view,
  }
}