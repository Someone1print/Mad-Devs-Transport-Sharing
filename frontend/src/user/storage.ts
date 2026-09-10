/**
 * The identity lives in sessionStorage on purpose: it survives reloads of the same tab, but a
 * new tab starts as a new user, so "two tabs, two riders" needs no incognito window.
 */
const KEY = 'transport-sharing.user'

export interface StoredUser {
  id: number
  name: string
}

export function loadStoredUser(): StoredUser | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as Partial<StoredUser>
    return typeof parsed.id === 'number' && typeof parsed.name === 'string'
      ? { id: parsed.id, name: parsed.name }
      : null
  } catch {
    return null
  }
}

export function saveStoredUser(user: StoredUser): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(user))
  } catch {
    // storage unavailable (private mode etc.): the session just will not survive a reload
  }
}

export function clearStoredUser(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // nothing to clear
  }
}
