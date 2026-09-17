import { request } from './client'
import type { Email, Ride } from './types'

export function fetchRideHistory(): Promise<Ride[]> {
  return request<Ride[]>('/api/rides')
}

export function fetchEmails(): Promise<Email[]> {
  return request<Email[]>('/api/emails')
}
