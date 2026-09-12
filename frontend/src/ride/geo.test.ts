import { describe, expect, it } from 'vitest'

import { pointInPolygon } from './geo'

const SQUARE = [
  { lat: 0, lon: 0 },
  { lat: 0, lon: 10 },
  { lat: 10, lon: 10 },
  { lat: 10, lon: 0 },
]

const C_SHAPE = [
  { lat: 0, lon: 0 },
  { lat: 0, lon: 10 },
  { lat: 10, lon: 10 },
  { lat: 10, lon: 7 },
  { lat: 4, lon: 7 },
  { lat: 4, lon: 3 },
  { lat: 10, lon: 3 },
  { lat: 10, lon: 0 },
]

describe('pointInPolygon (same algorithm as backend/app/geo.py)', () => {
  it('classifies inside and outside of a square', () => {
    expect(pointInPolygon({ lat: 5, lon: 5 }, SQUARE)).toBe(true)
    expect(pointInPolygon({ lat: -0.1, lon: 5 }, SQUARE)).toBe(false)
    expect(pointInPolygon({ lat: 50, lon: 50 }, SQUARE)).toBe(false)
  })

  it('counts boundary points as inside', () => {
    expect(pointInPolygon({ lat: 0, lon: 5 }, SQUARE)).toBe(true)
    expect(pointInPolygon({ lat: 10, lon: 10 }, SQUARE)).toBe(true)
  })

  it('handles a concave shape', () => {
    expect(pointInPolygon({ lat: 7, lon: 5 }, C_SHAPE)).toBe(false)
    expect(pointInPolygon({ lat: 2, lon: 5 }, C_SHAPE)).toBe(true)
    expect(pointInPolygon({ lat: 7, lon: 8.5 }, C_SHAPE)).toBe(true)
  })

  it('returns false for degenerate polygons', () => {
    expect(pointInPolygon({ lat: 0, lon: 0 }, [])).toBe(false)
  })
})
