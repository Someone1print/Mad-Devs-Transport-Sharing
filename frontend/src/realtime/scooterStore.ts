import type { Scooter } from '../api/types'

/** Immutable map of scooters by code; every change produces a new Map for React. */
export type ScooterStore = ReadonlyMap<string, Scooter>

export function emptyStore(): ScooterStore {
  return new Map()
}

function isStale(known: Scooter | undefined, incoming: Scooter): boolean {
  return known !== undefined && Date.parse(known.updated_at) > Date.parse(incoming.updated_at)
}

/** Apply one update; returns the same store when the update is older than what we know. */
export function applyScooter(store: ScooterStore, incoming: Scooter): ScooterStore {
  if (isStale(store.get(incoming.code), incoming)) {
    return store
  }
  const next = new Map(store)
  next.set(incoming.code, incoming)
  return next
}

/** Merge a full list (initial load or resync) without overwriting newer live updates. */
export function applyScooters(store: ScooterStore, scooters: Scooter[]): ScooterStore {
  return scooters.reduce(applyScooter, store)
}
