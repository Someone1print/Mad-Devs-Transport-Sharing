/**
 * Who this tab rides as, and who this browser has ridden as.
 *
 * The tab's identity lives in sessionStorage: it survives reloads of the same tab, and a second
 * tab can be a second rider ("two tabs, two riders" without an incognito window). The browser's
 * riders live in localStorage, most recent first, so a tab that was closed mid-ride comes back:
 * a fresh tab continues as the most recent rider, and the sign-in screen offers the others.
 */
const TAB_KEY = 'transport-sharing.user'
const RIDERS_KEY = 'transport-sharing.riders'
const RIDERS_MAX = 5

export interface StoredUser {
  id: number
  name: string
}

function parseUser(raw: unknown): StoredUser | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const parsed = raw as Partial<StoredUser>
  return typeof parsed.id === 'number' && typeof parsed.name === 'string'
    ? { id: parsed.id, name: parsed.name }
    : null
}

function readJson(storage: Storage, key: string): unknown {
  try {
    const raw = storage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeJson(storage: Storage, key: string, value: unknown): void {
  try {
    storage.setItem(key, JSON.stringify(value))
  } catch {
    // storage unavailable (private mode etc.): the identity just will not survive
  }
}

/** Riders this browser has registered, most recent first. */
export function loadKnownRiders(): StoredUser[] {
  const raw = readJson(localStorage, RIDERS_KEY)
  return Array.isArray(raw) ? raw.map(parseUser).filter((u): u is StoredUser => u !== null) : []
}

/** This tab's rider, else the browser's most recent one (the tab was closed and reopened). */
export function loadStoredUser(): StoredUser | null {
  return parseUser(readJson(sessionStorage, TAB_KEY)) ?? loadKnownRiders()[0] ?? null
}

/** The tab now rides as `user`; the browser remembers them as the most recent rider. */
export function saveStoredUser(user: StoredUser): void {
  writeJson(sessionStorage, TAB_KEY, user)
  const others = loadKnownRiders().filter((r) => r.id !== user.id)
  writeJson(localStorage, RIDERS_KEY, [user, ...others].slice(0, RIDERS_MAX))
}

/** «Сменить»: this tab stops being anyone; the browser still remembers the rider. */
export function clearStoredUser(): void {
  try {
    sessionStorage.removeItem(TAB_KEY)
  } catch {
    // nothing to clear
  }
}

/** The server no longer knows this id (the database was reset): forget it everywhere. */
export function forgetRider(id: number): void {
  clearStoredUser()
  writeJson(
    localStorage,
    RIDERS_KEY,
    loadKnownRiders().filter((r) => r.id !== id),
  )
}
