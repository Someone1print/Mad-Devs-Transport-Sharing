import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearStoredUser,
  forgetRider,
  loadKnownRiders,
  loadStoredUser,
  saveStoredUser,
} from './storage'

function fakeStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length() {
      return map.size
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => void map.delete(key),
    setItem: (key: string, value: string) => void map.set(key, String(value)),
  }
}

const aibek = { id: 1, name: 'Айбек' }
const dana = { id: 2, name: 'Дана' }

describe('identity storage', () => {
  beforeEach(() => {
    vi.stubGlobal('sessionStorage', fakeStorage())
    vi.stubGlobal('localStorage', fakeStorage())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('a tab keeps its own rider even when the browser registered someone newer', () => {
    saveStoredUser(aibek)
    const tabA = sessionStorage.getItem('transport-sharing.user')
    saveStoredUser(dana) // another tab registered Dana: the browser's most recent rider
    sessionStorage.setItem('transport-sharing.user', tabA!) // back in tab A

    expect(loadStoredUser()).toEqual(aibek)
    expect(loadKnownRiders()).toEqual([dana, aibek])
  })

  it('a fresh tab (closed and reopened) continues as the most recent rider', () => {
    saveStoredUser(aibek)
    saveStoredUser(dana)
    vi.stubGlobal('sessionStorage', fakeStorage()) // a new tab has no session identity

    expect(loadStoredUser()).toEqual(dana)
  })

  it('«сменить» frees the tab but the browser still offers the rider', () => {
    saveStoredUser(aibek)
    clearStoredUser()

    expect(sessionStorage.getItem('transport-sharing.user')).toBeNull()
    expect(loadKnownRiders()).toEqual([aibek])
    expect(loadStoredUser()).toEqual(aibek) // the fallback again, until someone registers
  })

  it('an id the server no longer knows is forgotten everywhere', () => {
    saveStoredUser(aibek)
    saveStoredUser(dana)
    forgetRider(dana.id)

    expect(loadKnownRiders()).toEqual([aibek])
    expect(loadStoredUser()).toEqual(aibek)
  })

  it('re-registering an existing rider moves them to the front; the list stays short', () => {
    for (let id = 1; id <= 7; id++) {
      saveStoredUser({ id, name: `Rider ${id}` })
    }
    saveStoredUser({ id: 3, name: 'Rider 3' })

    expect(loadKnownRiders().map((r) => r.id)).toEqual([3, 7, 6, 5, 4])
  })

  it('survives storage that throws or holds garbage', () => {
    vi.stubGlobal('localStorage', {
      ...fakeStorage(),
      getItem: () => {
        throw new Error('blocked')
      },
    })
    sessionStorage.setItem('transport-sharing.user', '{"id":"1"}')

    expect(loadStoredUser()).toBeNull()
    expect(loadKnownRiders()).toEqual([])
    expect(() => saveStoredUser(aibek)).not.toThrow()
  })
})
