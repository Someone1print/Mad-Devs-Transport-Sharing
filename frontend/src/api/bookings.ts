import { request } from './client'
import type { Booking } from './types'

export function fetchActiveBooking(): Promise<Booking | null> {
  return request<Booking | null>('/api/bookings/active')
}

export function createBooking(scooterCode: string): Promise<Booking> {
  return request<Booking>('/api/bookings', { method: 'POST', body: { scooter_code: scooterCode } })
}

export function cancelBooking(bookingId: number): Promise<Booking> {
  return request<Booking>(`/api/bookings/${bookingId}/cancel`, { method: 'POST' })
}
