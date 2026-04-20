import type { JobEvent } from '../../types/project'

export type GenerationPhaseId = 'solver' | 'builder' | 'export'
export type GenerationPhaseStatus = 'pending' | 'running' | 'success' | 'error'

export type GenerationPhase = {
  id: GenerationPhaseId
  status: GenerationPhaseStatus
  startedAt: string | null
  endedAt: string | null
  durationMs: number | null
}

export type GenerationFailure = {
  code: string | null
  message: string | null
  infeasible: boolean
}

const FEASIBLE_STATUSES = new Set(['OPTIMAL', 'FEASIBLE', 'optimal', 'feasible'])

function getEvent(events: JobEvent[], name: string): JobEvent | undefined {
  return events.find((event) => event.event === name)
}

function getStringData(event: JobEvent | undefined, key: string): string | null {
  if (!event) {
    return null
  }

  const value = event.data[key]
  return typeof value === 'string' ? value : null
}

function toTimestamp(value: string | null): number | null {
  if (!value) {
    return null
  }

  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

function computeDuration(
  startedAt: string | null,
  endedAt: string | null,
  now: number,
  status: GenerationPhaseStatus,
): number | null {
  const startedMs = toTimestamp(startedAt)
  if (startedMs === null) {
    return null
  }

  const endedMs = endedAt ? toTimestamp(endedAt) : status === 'running' ? now : null
  if (endedMs === null) {
    return null
  }

  return Math.max(0, endedMs - startedMs)
}

function determineFailedPhase(events: JobEvent[]): GenerationPhaseId | null {
  const failedEvent = getEvent(events, 'failed')
  if (!failedEvent) {
    return null
  }

  const solverStatus = getStringData(getEvent(events, 'solver_finished'), 'status')
  if (solverStatus && !FEASIBLE_STATUSES.has(solverStatus)) {
    return 'solver'
  }

  if (getEvent(events, 'export_started')) {
    return 'export'
  }

  if (getEvent(events, 'builder_started')) {
    return 'builder'
  }

  if (getEvent(events, 'solver_started')) {
    return 'solver'
  }

  return null
}

export function getGenerationFailure(events: JobEvent[]): GenerationFailure | null {
  const failedEvent = getEvent(events, 'failed')
  if (!failedEvent) {
    return null
  }

  const code = getStringData(failedEvent, 'code')
  const message = getStringData(failedEvent, 'message')
  const solverStatus = getStringData(getEvent(events, 'solver_finished'), 'status')

  return {
    code,
    message,
    infeasible: code === 'INFEASIBLE_SOLUTION' || Boolean(solverStatus && !FEASIBLE_STATUSES.has(solverStatus)),
  }
}

export function getGenerationPhases(
  events: JobEvent[],
  jobStatus: string,
  now = Date.now(),
): GenerationPhase[] {
  const solverStarted = getEvent(events, 'solver_started')
  const solverFinished = getEvent(events, 'solver_finished')
  const builderStarted = getEvent(events, 'builder_started')
  const exportStarted = getEvent(events, 'export_started')
  const finished = getEvent(events, 'finished')
  const failed = getEvent(events, 'failed')
  const failedPhase = determineFailedPhase(events)

  const solverStatus: GenerationPhaseStatus = !solverStarted
    ? 'pending'
    : solverFinished
      ? failedPhase === 'solver'
        ? 'error'
        : 'success'
      : failedPhase === 'solver' || jobStatus === 'failed'
        ? 'error'
        : 'running'

  const builderStatus: GenerationPhaseStatus = !builderStarted
    ? 'pending'
    : exportStarted || finished
      ? failedPhase === 'builder'
        ? 'error'
        : 'success'
      : failedPhase === 'builder'
        ? 'error'
        : 'running'

  const exportStatus: GenerationPhaseStatus = !exportStarted
    ? 'pending'
    : finished
      ? 'success'
      : failedPhase === 'export'
        ? 'error'
        : 'running'

  const solverEndedAt = solverFinished?.timestamp ?? (failedPhase === 'solver' ? failed?.timestamp ?? null : null)
  const builderEndedAt = exportStarted?.timestamp ?? (failedPhase === 'builder' ? failed?.timestamp ?? null : null)
  const exportEndedAt = finished?.timestamp ?? (failedPhase === 'export' ? failed?.timestamp ?? null : null)

  const phases: GenerationPhase[] = [
    {
      id: 'solver',
      status: solverStatus,
      startedAt: solverStarted?.timestamp ?? null,
      endedAt: solverEndedAt,
      durationMs: computeDuration(solverStarted?.timestamp ?? null, solverEndedAt, now, solverStatus),
    },
    {
      id: 'builder',
      status: builderStatus,
      startedAt: builderStarted?.timestamp ?? null,
      endedAt: builderEndedAt,
      durationMs: computeDuration(builderStarted?.timestamp ?? null, builderEndedAt, now, builderStatus),
    },
    {
      id: 'export',
      status: exportStatus,
      startedAt: exportStarted?.timestamp ?? null,
      endedAt: exportEndedAt,
      durationMs: computeDuration(exportStarted?.timestamp ?? null, exportEndedAt, now, exportStatus),
    },
  ]

  return phases
}