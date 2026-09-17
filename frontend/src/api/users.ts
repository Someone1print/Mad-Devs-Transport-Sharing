import { request } from './client'
import type { User } from './types'

/** Who the session cookie belongs to; 401 when nobody is signed in. */
export function fetchMe(): Promise<User> {
  return request<User>('/api/users/me')
}
