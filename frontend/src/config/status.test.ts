import { describe, expect, it } from 'vitest'

import type { ScooterStatus } from '../api/types'
import { STATUS_META, STATUS_ORDER } from './status'

const ALL: ScooterStatus[] = ['available', 'reserved', 'riding', 'unavailable']

describe('STATUS_META', () => {
  it('describes every status with a label and a colour', () => {
    for (const status of ALL) {
      expect(STATUS_META[status].label).toBeTruthy()
      expect(STATUS_META[status].color).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })

  it('uses distinct colours so statuses cannot be confused on the map', () => {
    const colours = new Set(ALL.map((status) => STATUS_META[status].color))

    expect(colours.size).toBe(ALL.length)
  })

  it('lists every status once for the legend', () => {
    expect([...STATUS_ORDER].sort()).toEqual([...ALL].sort())
  })
})
