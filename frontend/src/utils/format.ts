import type { Point2D } from '../types/project'

export function formatArea(value: number): string {
  return `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(value)} m²`
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function polygonArea(points: Point2D[]): number {
  if (points.length < 3) {
    return 0
  }

  let signedArea = 0
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index]
    const next = points[(index + 1) % points.length]
    signedArea += current.x * next.y - next.x * current.y
  }

  return Math.abs(signedArea) / 2
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}