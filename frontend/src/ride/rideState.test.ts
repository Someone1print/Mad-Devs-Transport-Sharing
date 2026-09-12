import { describe, expect, it } from 'vitest'

import type { Ride, RideEvent } from '../api/types'
import { applyRideEvent, rideErrorMessage } from './rideState'

function ride(overrides: Partial<Ride> = {}): Ride {
  return {
    id: 3,
    scooter_code: 'KG-001',
    user_id: 7,
    status: 'active',
    started_at: '2026-09-12T10:00:00Z',
    finished_at: null,
    ride_rate_per_minute: '5.00',
    pause_rate_per_minute: '1.50',
    segments: [],
    receipt: null,
    ...overrides,
  }
}

describe('applyRideEvent', () => {
  it('stores the ride on start and replaces it on pause/resume', () => {
    const started: RideEvent = { type: 'ride.started', ride: ride() }
    const paused: RideEvent = { type: 'ride.paused', ride: ride({ status: 'paused' }) }

    expect(applyRideEvent(null, started)).toEqual(ride())
    expect(applyRideEvent(ride(), paused)?.status).toBe('paused')
  })

  it('keeps the finished ride so the receipt can be shown', () => {
    const finished: RideEvent = { type: 'ride.finished', ride: ride({ status: 'finished' }) }

    expect(applyRideEvent(ride(), finished)?.status).toBe('finished')
  })

  it('ignores events about a different ride than the one in progress', () => {
    const other: RideEvent = { type: 'ride.paused', ride: ride({ id: 99, status: 'paused' }) }

    expect(applyRideEvent(ride(), other)).toEqual(ride())
  })
})

describe('rideErrorMessage', () => {
  it('translates the zone refusal and other known codes', () => {
    expect(rideErrorMessage('outside_service_zone', 'Вы вне зоны обслуживания, вернитесь')).toMatch(
      /вне зоны/,
    )
    expect(rideErrorMessage('booking_not_active')).toMatch(/Бронь/)
    expect(rideErrorMessage('user_has_active_ride')).toMatch(/поездка/)
  })

  it('falls back to the server message', () => {
    expect(rideErrorMessage('weird', 'Server text')).toBe('Server text')
  })
})
