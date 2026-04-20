import type { Point2D } from '../../types/project'

export const MIN_POLYGON_POINTS = 3
export const MIN_AREA_M2 = 50

export type SolarValidationErrors = {
  tooFewPoints?: string
  selfIntersecting?: string
  tooSmall?: string
}

export type SolarValidationResult = {
  valid: boolean
  errors: SolarValidationErrors
}

function orientation(p: Point2D, q: Point2D, r: Point2D): -1 | 0 | 1 {
  const val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)
  if (Math.abs(val) < 1e-10) return 0
  return val > 0 ? 1 : -1
}

function onSegment(p: Point2D, q: Point2D, r: Point2D): boolean {
  return (
    q.x >= Math.min(p.x, r.x) &&
    q.x <= Math.max(p.x, r.x) &&
    q.y >= Math.min(p.y, r.y) &&
    q.y <= Math.max(p.y, r.y)
  )
}

function segmentsIntersect(p1: Point2D, q1: Point2D, p2: Point2D, q2: Point2D): boolean {
  const o1 = orientation(p1, q1, p2)
  const o2 = orientation(p1, q1, q2)
  const o3 = orientation(p2, q2, p1)
  const o4 = orientation(p2, q2, q1)

  if (o1 !== o2 && o3 !== o4) return true

  if (o1 === 0 && onSegment(p1, p2, q1)) return true
  if (o2 === 0 && onSegment(p1, q2, q1)) return true
  if (o3 === 0 && onSegment(p2, p1, q2)) return true
  if (o4 === 0 && onSegment(p2, q1, q2)) return true

  return false
}

export function isSelfIntersecting(points: Point2D[]): boolean {
  if (points.length < 4) return false
  const n = points.length
  for (let i = 0; i < n; i++) {
    const ni = (i + 1) % n
    for (let j = i + 2; j < n; j++) {
      const nj = (j + 1) % n
      // Las aristas adyacentes comparten un vértice; no cuentan como intersección
      if (i === 0 && nj === 0) continue
      if (segmentsIntersect(points[i], points[ni], points[j], points[nj])) return true
    }
  }
  return false
}

export function polygonAreaM2(points: Point2D[]): number {
  if (points.length < 3) return 0
  let area = 0
  for (let i = 0; i < points.length; i++) {
    const curr = points[i]
    const next = points[(i + 1) % points.length]
    area += curr.x * next.y - next.x * curr.y
  }
  return Math.abs(area) / 2
}

export function validateSolar(points: Point2D[]): SolarValidationResult {
  const errors: SolarValidationErrors = {}

  if (points.length < MIN_POLYGON_POINTS) {
    errors.tooFewPoints = 'solar_editor.validation.too_few_points'
  }

  if (points.length >= MIN_POLYGON_POINTS && isSelfIntersecting(points)) {
    errors.selfIntersecting = 'solar_editor.validation.self_intersecting'
  }

  if (points.length >= MIN_POLYGON_POINTS && polygonAreaM2(points) < MIN_AREA_M2) {
    errors.tooSmall = 'solar_editor.validation.polygon_too_small'
  }

  return { valid: Object.keys(errors).length === 0, errors }
}
