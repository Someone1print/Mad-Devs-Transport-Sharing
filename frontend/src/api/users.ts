import { request } from './client'
import type { User } from './types'

export function createUser(name: string): Promise<User> {
  return request<User>('/api/users', { method: 'POST', body: { name } })
}

export function fetchMe(userId: number): Promise<User> {
  return request<User>('/api/users/me', { userId })
}
