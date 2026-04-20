import { describe, expect, it } from 'vitest'
import type { Point2D } from '../../types/project'
import {
  isSelfIntersecting,
  MIN_AREA_M2,
  MIN_POLYGON_POINTS,
  polygonAreaM2,
  validateSolar,
} from './solarValidation'

// ---------------------------------------------------------------------------
// Hilfsdaten
// ---------------------------------------------------------------------------

const SQUARE_20X30: Point2D[] = [
  { x: 0, y: 0 },
  { x: 20, y: 0 },
  { x: 20, y: 30 },
  { x: 0, y: 30 },
]

const TRIANGLE: Point2D[] = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 5, y: 8 },
]

// Schmetterlings-Polygon: die ersten beiden Kanten kreuzen sich
const BUTTERFLY: Point2D[] = [
  { x: 0, y: 0 },
  { x: 10, y: 10 },
  { x: 10, y: 0 },
  { x: 0, y: 10 },
]

// Sehr kleines Polygon (< 50 m²)
const TINY: Point2D[] = [
  { x: 0, y: 0 },
  { x: 6, y: 0 },
  { x: 6, y: 6 },
  { x: 0, y: 6 },
]

// L-förmiges Polygon ohne Selbstschnitt
const L_SHAPE: Point2D[] = [
  { x: 0, y: 0 },
  { x: 20, y: 0 },
  { x: 20, y: 15 },
  { x: 10, y: 15 },
  { x: 10, y: 30 },
  { x: 0, y: 30 },
]

// ---------------------------------------------------------------------------
// isSelfIntersecting
// ---------------------------------------------------------------------------

describe('isSelfIntersecting', () => {
  it('gibt false zurück für ein Rechteck', () => {
    expect(isSelfIntersecting(SQUARE_20X30)).toBe(false)
  })

  it('gibt false zurück für ein Dreieck (weniger als 4 Punkte)', () => {
    expect(isSelfIntersecting(TRIANGLE)).toBe(false)
  })

  it('gibt true zurück für ein Schmetterlings-Polygon', () => {
    expect(isSelfIntersecting(BUTTERFLY)).toBe(true)
  })

  it('gibt false zurück für ein L-förmiges Polygon', () => {
    expect(isSelfIntersecting(L_SHAPE)).toBe(false)
  })

  it('gibt false zurück für eine leere Punktliste', () => {
    expect(isSelfIntersecting([])).toBe(false)
  })

  it('gibt false zurück für genau 3 Punkte', () => {
    expect(isSelfIntersecting(TRIANGLE)).toBe(false)
  })

  it('erkennt Selbstschnitt bei einem Kreuz-Polygon', () => {
    // Polygon in Form eines X: P0→P1 kreuzt P2→P3
    const cross: Point2D[] = [
      { x: 0, y: 0 },
      { x: 10, y: 10 },
      { x: 10, y: 0 },
      { x: 0, y: 10 },
    ]
    expect(isSelfIntersecting(cross)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// polygonAreaM2
// ---------------------------------------------------------------------------

describe('polygonAreaM2', () => {
  it(`berechnet ${20 * 30} m² für ein 20×30-Rechteck`, () => {
    expect(polygonAreaM2(SQUARE_20X30)).toBeCloseTo(600, 5)
  })

  it('gibt 0 zurück für weniger als 3 Punkte', () => {
    expect(polygonAreaM2([{ x: 0, y: 0 }, { x: 5, y: 0 }])).toBe(0)
    expect(polygonAreaM2([])).toBe(0)
  })

  it('berechnet die Fläche eines Dreiecks korrekt', () => {
    // Fläche = 0.5 * Grundlinie * Höhe = 0.5 * 10 * 8 = 40 m²
    expect(polygonAreaM2(TRIANGLE)).toBeCloseTo(40, 5)
  })

  it('ist unabhängig von der Ausrichtung (UZS vs. GUZ)', () => {
    const cw = [...SQUARE_20X30].reverse()
    expect(polygonAreaM2(cw)).toBeCloseTo(600, 5)
  })
})

// ---------------------------------------------------------------------------
// validateSolar
// ---------------------------------------------------------------------------

describe('validateSolar', () => {
  it(`ist valid für ein Rechteck mit ≥ ${MIN_AREA_M2} m²`, () => {
    const result = validateSolar(SQUARE_20X30)
    expect(result.valid).toBe(true)
    expect(result.errors).toEqual({})
  })

  it(`setzt tooFewPoints wenn Punkte < ${MIN_POLYGON_POINTS}`, () => {
    const result = validateSolar([{ x: 0, y: 0 }, { x: 5, y: 0 }])
    expect(result.valid).toBe(false)
    expect(result.errors.tooFewPoints).toBeDefined()
  })

  it('setzt selfIntersecting für ein Schmetterlings-Polygon', () => {
    const result = validateSolar(BUTTERFLY)
    expect(result.valid).toBe(false)
    expect(result.errors.selfIntersecting).toBeDefined()
  })

  it(`setzt tooSmall wenn Fläche < ${MIN_AREA_M2} m²`, () => {
    const result = validateSolar(TINY)
    expect(result.valid).toBe(false)
    expect(result.errors.tooSmall).toBeDefined()
  })

  it('meldet keinen Selbstschnitt bei L-Form', () => {
    const result = validateSolar(L_SHAPE)
    expect(result.valid).toBe(true)
    expect(result.errors.selfIntersecting).toBeUndefined()
  })

  it('setzt nur tooFewPoints und keine anderen Fehler bei leerer Liste', () => {
    const result = validateSolar([])
    expect(result.errors.tooFewPoints).toBeDefined()
    expect(result.errors.selfIntersecting).toBeUndefined()
    expect(result.errors.tooSmall).toBeUndefined()
  })

  it('kann mehrere Fehler gleichzeitig zurückgeben', () => {
    // Kleines Schmetterlings-Polygon: selbstschneidend UND zu klein
    const smallButterfly: Point2D[] = [
      { x: 0, y: 0 },
      { x: 4, y: 4 },
      { x: 4, y: 0 },
      { x: 0, y: 4 },
    ]
    const result = validateSolar(smallButterfly)
    expect(result.valid).toBe(false)
    expect(result.errors.selfIntersecting).toBeDefined()
    expect(result.errors.tooSmall).toBeDefined()
  })
})
