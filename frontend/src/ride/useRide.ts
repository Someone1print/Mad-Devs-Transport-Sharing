import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { fetchActiveRide, finishRide, pauseRide, resumeRide, startRide } from '../api/rides'
import type { Ride, RideEvent } from '../api/types'
import type { ToastInput } from '../hooks/useToasts'
import { applyRideEvent, rideErrorMessage } from './rideState'

interface UseRideOptions {
  userId: number | null
  notify: (toast: ToastInput) => void
}

export interface RideActions {
  /** The ride in progress (active or paused). */
  active: Ride | null
  /** The last finished ride, kept until the receipt is dismissed. */
  finished: Ride | null
  busy: boolean
  /** Resolves to true when the ride is running after the call. */
  start: (bookingId: number) => Promise<boolean>
  /** Reload the active ride from the server (after a reconnect). */
  refresh: () => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  finish: () => Promise<void>
  dismissReceipt: () => void
  handleEvent: (event: RideEvent) => void
}

function describeError(error: unknown): string {
  return error instanceof ApiError
    ? rideErrorMessage(error.code, error.message)
    : rideErrorMessage('network')
}

/** The rider's ride: loaded on start, changed by the buttons and by personal ride events. */
export function useRide({ userId, notify }: UseRideOptions): RideActions {
  const [held, setHeld] = useState<{ userId: number | null; ride: Ride | null }>({
    userId: null,
    ride: null,
  })
  const [finished, setFinished] = useState<Ride | null>(null)
  const [busy, setBusy] = useState(false)
  const current = held.userId === userId ? held.ride : null
  const active = current !== null && current.status !== 'finished' ? current : null

  const setRide = useCallback(
    (update: Ride | null | ((known: Ride | null) => Ride | null)) => {
      setHeld((prev) => {
        const known = prev.userId === userId ? prev.ride : null
        const ride = typeof update === 'function' ? update(known) : update
        return { userId, ride }
      })
    },
    [userId],
  )

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      setRide(await fetchActiveRide(userId))
    } catch (error) {
      console.warn('Could not load the active ride', error)
    }
  }, [userId, setRide])

  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchActiveRide(userId)
      .then((ride) => {
        if (!cancelled) {
          setRide(ride)
        }
      })
      .catch((error: unknown) => console.warn('Could not load the active ride', error))
    return () => {
      cancelled = true
    }
  }, [userId, setRide])

  const handleEvent = useCallback(
    (event: RideEvent) => {
      setRide((known: Ride | null) => applyRideEvent(known, event))
      if (event.type === 'ride.finished') {
        setFinished(event.ride)
      }
    },
    [setRide],
  )

  const run = useCallback(
    async (action: () => Promise<Ride>, onDone?: (ride: Ride) => void): Promise<boolean> => {
      setBusy(true)
      try {
        const ride = await action()
        setRide(ride)
        onDone?.(ride)
        return true
      } catch (error) {
        notify({ kind: 'error', text: describeError(error) })
        if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
          void refresh() // our picture of the ride is stale: reload it from the server
        }
        return false
      } finally {
        setBusy(false)
      }
    },
    [notify, setRide, refresh],
  )

  const start = useCallback(
    async (bookingId: number) => {
      if (userId === null) {
        return false
      }
      return run(
        () => startRide(userId, bookingId),
        (ride) => notify({ kind: 'success', text: `Поездка на ${ride.scooter_code} началась` }),
      )
    },
    [userId, run, notify],
  )

  const pause = useCallback(async () => {
    if (userId === null || active === null) {
      return
    }
    await run(() => pauseRide(userId, active.id))
  }, [userId, active, run])

  const resume = useCallback(async () => {
    if (userId === null || active === null) {
      return
    }
    await run(() => resumeRide(userId, active.id))
  }, [userId, active, run])

  const finish = useCallback(async () => {
    if (userId === null || active === null) {
      return
    }
    await run(
      () => finishRide(userId, active.id),
      (ride) => setFinished(ride),
    )
  }, [userId, active, run])

  const dismissReceipt = useCallback(() => setFinished(null), [])

  return {
    active,
    finished,
    busy,
    start,
    refresh,
    pause,
    resume,
    finish,
    dismissReceipt,
    handleEvent,
  }
}
