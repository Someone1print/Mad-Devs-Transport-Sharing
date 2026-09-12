import { describe, expect, it } from 'vitest'

import type { Scooter } from '../api/types'
import { applyScooter, applyScooters, emptyStore } from './scooterStore'

function scooter(overrides: Partial<Scooter> = {}): Scooter {
  return {
    code: 'KG-001',
    lat: 42.87,
    lon: 74.59,
    battery: 80,
    status: 'available',
    paused: false,
    updated_at: '2026-09-09T10:00:00Z',
    ...overrides,
  }
}

describe('applyScooter', () => {
  it('adds an unknown scooter', () => {
    const store = applyScooter(emptyStore(), scooter())

    expect(store.get('KG-001')?.battery).toBe(80)
  })

  it('replaces the scooter with a newer update', () => {
    const store = applyScooter(emptyStore(), scooter())

    const next = applyScooter(store, scooter({ battery: 70, updated_at: '2026-09-09T10:00:05Z' }))

    expect(next.get('KG-001')?.battery).toBe(70)
    expect(next).not.toBe(store)
  })

  it('ignores an update older than the known state', () => {
    const store = applyScooter(emptyStore(), scooter({ updated_at: '2026-09-09T10:00:05Z' }))

    const next = applyScooter(store, scooter({ battery: 5, updated_at: '2026-09-09T10:00:00Z' }))

    expect(next).toBe(store)
    expect(next.get('KG-001')?.battery).toBe(80)
  })
})

describe('applyScooters', () => {
  it('merges the initial list without losing newer live updates', () => {
    const live = applyScooter(
      emptyStore(),
      scooter({ code: 'KG-002', battery: 30, updated_at: '2026-09-09T10:00:09Z' }),
    )

    const store = applyScooters(live, [
      scooter({ code: 'KG-001' }),
      scooter({ code: 'KG-002', battery: 60, updated_at: '2026-09-09T10:00:01Z' }),
    ])

    expect([...store.keys()].sort()).toEqual(['KG-001', 'KG-002'])
    expect(store.get('KG-002')?.battery).toBe(30)
  })
})
