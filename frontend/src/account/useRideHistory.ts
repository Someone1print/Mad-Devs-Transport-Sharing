import { useCallback, useEffect, useState } from 'react'

import { fetchRideHistory } from '../api/account'
import type { Ride } from '../api/types'

export type LoadStatus = 'loading' | 'ready' | 'error'

export interface RideHistory {
  rides: Ride[]
  status: LoadStatus
  refresh: () => Promise<void>
}

interface HistoryState {
  userId: number | null
  rides: Ride[]
  status: LoadStatus
}

/**
 * Finished rides with their server receipts. `version` is the id of the last ride that finished
 * (from the socket event or the finish response, whichever comes first), so the list follows
 * without a manual reload; `refresh` covers a reconnect and the "retry" button.
 */
export function useRideHistory(userId: number | null, version: number): RideHistory {
  const [state, setState] = useState<HistoryState>({ userId: null, rides: [], status: 'loading' })
  const current = state.userId === userId ? state : null

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      const rides = await fetchRideHistory(userId)
      setState({ userId, rides, status: 'ready' })
    } catch (error) {
      console.warn('Could not load the ride history', error)
      setState((prev) => ({
        userId,
        rides: prev.userId === userId ? prev.rides : [],
        status: 'error',
      }))
    }
  }, [userId])

  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchRideHistory(userId)
      .then((rides) => {
        if (!cancelled) {
          setState({ userId, rides, status: 'ready' })
        }
      })
      .catch((error: unknown) => {
        console.warn('Could not load the ride history', error)
        if (!cancelled) {
          setState((prev) => ({
            userId,
            rides: prev.userId === userId ? prev.rides : [],
            status: 'error',
          }))
        }
      })
    return () => {
      cancelled = true
    }
  }, [userId, version])

  return {
    rides: current?.rides ?? [],
    status: current?.status ?? 'loading',
    refresh,
  }
}
