import { request } from './client'
import type { User } from './types'

/** The signed-in user; the session token also arrives as an HttpOnly cookie, which the browser uses. */
export interface AuthResult {
  user: User
  token: string
}

export function registerAccount(name: string, email: string, password: string): Promise<AuthResult> {
  return request<AuthResult>('/api/auth/register', { method: 'POST', body: { name, email, password } })
}

export function login(email: string, password: string): Promise<AuthResult> {
  return request<AuthResult>('/api/auth/login', { method: 'POST', body: { email, password } })
}

export function logout(): Promise<void> {
  return request<void>('/api/auth/logout', { method: 'POST' })
}

export function changePassword(currentPassword: string, newPassword: string): Promise<User> {
  return request<User>('/api/users/me/password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
}
