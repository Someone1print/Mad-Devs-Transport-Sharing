import { request } from './client'
import type { Booking } from './types'

export function fetchActiveBooking(userId: number): Promise<Booking | null> {
  return request<Booking | null>('/api/bookings/active', { userId })
}

export function createBooking(userId: number, scooterCode: string): Promise<Booking> {
  return request<Booking>('/api/bookings', {
    method: 'POST',
    body: { scooter_code: scooterCode },
    userId,
  })
}

export function cancelBooking(userId: number, bookingId: number): Promise<Booking> {
  return request<Booking>(`/api/bookings/${bookingId}/cancel`, { method: 'POST', userId })
}
