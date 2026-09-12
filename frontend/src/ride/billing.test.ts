import { describe, expect, it } from 'vitest'

import type { Ride } from '../api/types'
import {
  formatMoney,
  liveEstimate,
  parseMoney,
  segmentCostKopecks,
  segmentSeconds,
} from './billing'

/** Same vectors as backend/tests/test_billing.py — keep them in sync. */
const VECTORS: Array<[string, number, string]> = [
  ['5.00', 0, '0.00'],
  ['5.00', 1, '0.08'],
  ['5.00', 59, '4.92'],
  ['5.00', 60, '5.00'],
  ['5.00', 61, '5.08'],
  ['5.00', 90, '7.50'],
  ['5.00', 119, '9.92'],
  ['5.00', 120, '10.00'],
  ['1.50', 1, '0.03'],
  ['1.50', 30, '0.75'],
  ['7.50', 1, '0.13'],
  ['0.01', 1, '0.00'],
  ['0.01', 30, '0.01'],
  // ties and near-ties that a wrong evaluation order or a float rate would get wrong
  ['1.50', 11, '0.28'],
  ['2.45', 30, '1.23'],
  ['1.15', 30, '0.58'],
  ['0.29', 60, '0.29'],
]

describe('segmentCostKopecks', () => {
  it.each(VECTORS)('rate %s for %i s costs %s', (rate, seconds, expected) => {
    expect(formatMoney(segmentCostKopecks(parseMoney(rate), seconds))).toBe(expected)
  })

  it('works in integer kopecks only', () => {
    expect(parseMoney('5.00')).toBe(500)
    expect(parseMoney('0.08')).toBe(8)
    expect(parseMoney('12')).toBe(1200)
    expect(parseMoney('1.15')).toBe(115) // Number('1.15') * 100 would give 114.99999999999999
    expect(parseMoney('0.5')).toBe(50)
    expect(formatMoney(1419)).toBe('14.19')
    expect(formatMoney(5)).toBe('0.05')
  })

  it('keeps the sign and ignores digits beyond the kopeck', () => {
    expect(parseMoney('-1.50')).toBe(-150)
    expect(parseMoney('0.129')).toBe(12)
    expect(formatMoney(-150)).toBe('-1.50')
  })
})

describe('segmentSeconds', () => {
  it('floors to whole seconds', () => {
    const start = Date.parse('2026-09-12T10:00:00Z')

    expect(segmentSeconds(start, start + 59_999)).toBe(59)
    expect(segmentSeconds(start, start + 60_000)).toBe(60)
    expect(segmentSeconds(start, start - 1000)).toBe(0)
  })
})

function ride(overrides: Partial<Ride> = {}): Ride {
  return {
    id: 1,
    scooter_code: 'KG-001',
    user_id: 7,
    status: 'active',
    started_at: '2026-09-12T10:00:00Z',
    finished_at: null,
    ride_rate_per_minute: '5.00',
    pause_rate_per_minute: '1.50',
    segments: [
      {
        kind: 'ride',
        started_at: '2026-09-12T10:00:00Z',
        ended_at: '2026-09-12T10:01:30Z',
        seconds: 90,
        cost: '7.50',
      },
      {
        kind: 'pause',
        started_at: '2026-09-12T10:01:30Z',
        ended_at: null,
        seconds: null,
        cost: null,
      },
    ],
    receipt: null,
    ...overrides,
  }
}

describe('liveEstimate', () => {
  it('adds the open segment at its own rate to the closed segments', () => {
    const now = Date.parse('2026-09-12T10:02:30Z') // pause open for 60 s → 1.50

    const estimate = liveEstimate(ride(), now)

    expect(estimate).toEqual({
      rideSeconds: 90,
      pauseSeconds: 60,
      rideKopecks: 750,
      pauseKopecks: 150,
      totalKopecks: 900,
    })
  })

  it('matches the backend receipt vector for a multi-pause ride', () => {
    // backend test: ride 90 → 7.50, pause 60 → 1.50, ride 61 → 5.08, pause 1 → 0.03, ride 1 → 0.08
    const segments: Ride['segments'] = [
      { kind: 'ride', started_at: '2026-09-12T10:00:00Z', ended_at: '2026-09-12T10:01:30Z', seconds: 90, cost: '7.50' },
      { kind: 'pause', started_at: '2026-09-12T10:01:30Z', ended_at: '2026-09-12T10:02:30Z', seconds: 60, cost: '1.50' },
      { kind: 'ride', started_at: '2026-09-12T10:02:30Z', ended_at: '2026-09-12T10:03:31Z', seconds: 61, cost: '5.08' },
      { kind: 'pause', started_at: '2026-09-12T10:03:31Z', ended_at: '2026-09-12T10:03:32Z', seconds: 1, cost: '0.03' },
      { kind: 'ride', started_at: '2026-09-12T10:03:32Z', ended_at: null, seconds: null, cost: null },
    ]
    const now = Date.parse('2026-09-12T10:03:33Z')

    const estimate = liveEstimate(ride({ segments }), now)

    expect(formatMoney(estimate.totalKopecks)).toBe('14.19')
    expect(estimate.rideSeconds).toBe(152)
    expect(estimate.pauseSeconds).toBe(61)
  })

  it('uses the receipt when the ride is finished', () => {
    const finished = ride({
      status: 'finished',
      receipt: {
        ride_seconds: 90,
        pause_seconds: 0,
        ride_cost: '7.50',
        pause_cost: '0.00',
        total_cost: '7.50',
        currency: 'KGS',
      },
    })

    expect(liveEstimate(finished, Date.now()).totalKopecks).toBe(750)
  })
})
