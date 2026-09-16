import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetRide, recallRide, rememberRide } from './rideMemory'

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

describe('ride memory', () => {
  beforeEach(() => vi.stubGlobal('localStorage', fakeStorage()))
  afterEach(() => vi.unstubAllGlobals())

  it('remembers the active ride per rider and forgets it once it ended', () => {
    rememberRide(1, 41)
    rememberRide(2, 42)

    expect(recallRide(1)).toBe(41)
    expect(recallRide(2)).toBe(42)
    forgetRide(1)
    expect(recallRide(1)).toBeNull()
    expect(recallRide(2)).toBe(42) // another rider's memory is untouched
  })

  it('ignores garbage and a missing store', () => {
    localStorage.setItem('transport-sharing.active-ride.1', 'seven')
    expect(recallRide(1)).toBeNull()

    vi.stubGlobal('localStorage', {
      ...fakeStorage(),
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    })
    expect(() => rememberRide(1, 5)).not.toThrow()
    expect(recallRide(1)).toBeNull()
  })
})
