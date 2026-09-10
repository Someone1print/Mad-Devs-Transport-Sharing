import { describe, expect, it } from 'vitest'

import type { Booking, BookingEvent } from '../api/types'
import {
  applyBookingEvent,
  bookingErrorMessage,
  formatRemaining,
  remainingSeconds,
  warningWindowSeconds,
} from './bookingState'

function booking(overrides: Partial<Booking> = {}): Booking {
  return {
    id: 1,
    scooter_code: 'KG-001',
    user_id: 7,
    status: 'active',
    created_at: '2026-09-10T10:00:00Z',
    expires_at: '2026-09-10T10:15:00Z',
    ...overrides,
  }
}

describe('applyBookingEvent', () => {
  it('stores the booking from booking.created', () => {
    const event: BookingEvent = { type: 'booking.created', booking: booking() }

    expect(applyBookingEvent(null, event)).toEqual(booking())
  })

  it('clears the active booking when it is cancelled or expired', () => {
    const cancelled: BookingEvent = {
      type: 'booking.cancelled',
      booking: booking({ status: 'cancelled' }),
    }
    const expired: BookingEvent = { type: 'booking.expired', booking: booking({ status: 'expired' }) }

    expect(applyBookingEvent(booking(), cancelled)).toBeNull()
    expect(applyBookingEvent(booking(), expired)).toBeNull()
  })

  it('ignores end events about a different booking', () => {
    const other: BookingEvent = {
      type: 'booking.expired',
      booking: booking({ id: 99, status: 'expired' }),
    }

    expect(applyBookingEvent(booking(), other)).toEqual(booking())
  })

  it('keeps the booking on the expiring warning', () => {
    const warning: BookingEvent = {
      type: 'booking.expiring',
      booking: booking(),
      seconds_left: 170,
    }

    expect(applyBookingEvent(booking(), warning)).toEqual(booking())
  })
})

describe('countdown helpers', () => {
  it('computes remaining seconds and never goes negative', () => {
    const now = Date.parse('2026-09-10T10:10:30Z')

    expect(remainingSeconds(booking(), now)).toBe(270)
    expect(remainingSeconds(booking(), now + 10 * 60_000)).toBe(0)
  })

  it('formats seconds as mm:ss', () => {
    expect(formatRemaining(270)).toBe('04:30')
    expect(formatRemaining(5)).toBe('00:05')
    expect(formatRemaining(0)).toBe('00:00')
  })
})

describe('warningWindowSeconds', () => {
  it('uses the configured window for a normal booking', () => {
    expect(warningWindowSeconds(booking(), 180)).toBe(180) // 15-minute booking
  })

  it('never warns earlier than half of a short booking', () => {
    const short = booking({ expires_at: '2026-09-10T10:01:00Z' }) // 60 s long

    expect(warningWindowSeconds(short, 180)).toBe(30)
    expect(warningWindowSeconds(short, 20)).toBe(20)
  })
})

describe('bookingErrorMessage', () => {
  it('translates known error codes', () => {
    expect(bookingErrorMessage('scooter_not_available')).toMatch(/другим пользователем/)
    expect(bookingErrorMessage('user_has_active_booking')).toMatch(/уже есть активная бронь/)
  })

  it('falls back to the server message or a generic text', () => {
    expect(bookingErrorMessage('weird_code', 'Server says no')).toBe('Server says no')
    expect(bookingErrorMessage('weird_code')).toMatch(/Не удалось/)
  })
})
