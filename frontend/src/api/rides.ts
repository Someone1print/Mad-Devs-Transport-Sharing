import { request } from './client'
import type { Ride, Zone } from './types'

export function fetchActiveRide(): Promise<Ride | null> {
  return request<Ride | null>('/api/rides/active')
}

export function fetchRide(rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}`)
}

export function startRide(bookingId: number): Promise<Ride> {
  return request<Ride>('/api/rides', { method: 'POST', body: { booking_id: bookingId } })
}

export function pauseRide(rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/pause`, { method: 'POST' })
}

export function resumeRide(rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/resume`, { method: 'POST' })
}

export function finishRide(rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/finish`, { method: 'POST' })
}

export function fetchZones(): Promise<Zone[]> {
  return request<Zone[]>('/api/zones')
}
