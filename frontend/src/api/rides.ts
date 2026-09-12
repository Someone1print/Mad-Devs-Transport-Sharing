import { request } from './client'
import type { Ride, Zone } from './types'

export function fetchActiveRide(userId: number): Promise<Ride | null> {
  return request<Ride | null>('/api/rides/active', { userId })
}

export function startRide(userId: number, bookingId: number): Promise<Ride> {
  return request<Ride>('/api/rides', { method: 'POST', body: { booking_id: bookingId }, userId })
}

export function pauseRide(userId: number, rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/pause`, { method: 'POST', userId })
}

export function resumeRide(userId: number, rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/resume`, { method: 'POST', userId })
}

export function finishRide(userId: number, rideId: number): Promise<Ride> {
  return request<Ride>(`/api/rides/${rideId}/finish`, { method: 'POST', userId })
}

export function fetchZones(): Promise<Zone[]> {
  return request<Zone[]>('/api/zones')
}
