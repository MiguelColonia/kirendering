import { describe, expect, it } from 'vitest'
import { getRenderProgress } from './renderProgress'

const STARTED_AT = '2026-04-21T12:00:00.000Z'

describe('getRenderProgress', () => {
  it('berechnet Fortschritt und Restzeit aus render_started', () => {
    const result = getRenderProgress(
      [
        {
          event: 'render_started',
          job_id: 'job-1',
          timestamp: STARTED_AT,
          data: {
            estimated_total_seconds: 120,
            view: 'exterior',
          },
        },
      ],
      'running',
      Date.parse(STARTED_AT) + 30_000,
    )

    expect(result.percent).toBeCloseTo(25, 0)
    expect(result.remainingSeconds).toBe(90)
    expect(result.view).toBe('exterior')
  })

  it('liefert 100 Prozent für abgeschlossene Jobs', () => {
    const result = getRenderProgress(
      [
        {
          event: 'render_started',
          job_id: 'job-2',
          timestamp: STARTED_AT,
          data: {
            estimated_total_seconds: 90,
            view: 'interior',
          },
        },
      ],
      'finished',
      Date.parse(STARTED_AT) + 10_000,
    )

    expect(result.percent).toBe(100)
    expect(result.remainingSeconds).toBe(0)
  })
})