import { useCallback, useEffect, useState } from 'react'

import { fetchRideHistory } from '../api/account'
import type { Ride } from '../api/types'

export interface RideHistory {
  rides: Ride[]
  loading: boolean
  refresh: () => Promise<void>
}

interface HistoryState {
  userId: number | null
  rides: Ride[]
  loaded: boolean
}

/** Finished rides with their server receipts; reloaded whenever a ride finishes. */
export function useRideHistory(userId: number | null, version: number): RideHistory {
  const [state, setState] = useState<HistoryState>({ userId: null, rides: [], loaded: false })
  const current = state.userId === userId ? state : null

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      const rides = await fetchRideHistory(userId)
      setState({ userId, rides, loaded: true })
    } catch (error) {
      console.warn('Could not load the ride history', error)
    }
  }, [userId])

  // `version` bumps when a ride finishes, so the history follows without a manual reload
  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchRideHistory(userId)
      .then((rides) => {
        if (!cancelled) {
          setState({ userId, rides, loaded: true })
        }
      })
      .catch((error: unknown) => console.warn('Could not load the ride history', error))
    return () => {
      cancelled = true
    }
  }, [userId, version])

  return {
    rides: current?.rides ?? [],
    loading: userId !== null && !(current?.loaded ?? false),
    refresh,
  }
}
