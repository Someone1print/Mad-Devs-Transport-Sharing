import { request } from './client'
import type { Email, Ride } from './types'

export function fetchRideHistory(userId: number): Promise<Ride[]> {
  return request<Ride[]>('/api/rides', { userId })
}

export function fetchEmails(userId: number): Promise<Email[]> {
  return request<Email[]>('/api/emails', { userId })
}
