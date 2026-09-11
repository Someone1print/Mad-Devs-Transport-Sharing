import { useCallback, useEffect, useState } from 'react'

import { cancelBooking, createBooking, fetchActiveBooking } from '../api/bookings'
import { ApiError } from '../api/client'
import type { Booking, BookingEvent } from '../api/types'
import type { ToastInput } from '../hooks/useToasts'
import { applyBookingEvent, bookingErrorMessage, formatRemaining } from './bookingState'

interface UseBookingOptions {
  userId: number | null
  notify: (toast: ToastInput) => void
}

export interface BookingActions {
  active: Booking | null
  busy: boolean
  book: (scooterCode: string) => Promise<void>
  cancel: () => Promise<void>
  handleEvent: (event: BookingEvent) => void
}

function describeError(error: unknown): string {
  return error instanceof ApiError
    ? bookingErrorMessage(error.code, error.message)
    : bookingErrorMessage('network')
}

function expiryTime(booking: Booking): string {
  return new Date(booking.expires_at).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** The rider's active booking: loaded on start, changed by actions and by personal events. */
export function useBooking({ userId, notify }: UseBookingOptions): BookingActions {
  // The booking is remembered together with the rider it belongs to, so switching riders
  // (sign out, new registration) derives "no booking" without an extra effect.
  const [held, setHeld] = useState<{ userId: number | null; booking: Booking | null }>({
    userId: null,
    booking: null,
  })
  const [busy, setBusy] = useState(false)
  const active = held.userId === userId ? held.booking : null
  const setActive = useCallback(
    (update: Booking | null | ((current: Booking | null) => Booking | null)) => {
      setHeld((current) => {
        const known = current.userId === userId ? current.booking : null
        const booking = typeof update === 'function' ? update(known) : update
        return { userId, booking }
      })
    },
    [userId],
  )

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      setActive(await fetchActiveBooking(userId))
    } catch (error) {
      console.warn('Could not load the active booking', error)
    }
  }, [userId, setActive])

  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchActiveBooking(userId)
      .then((booking) => {
        if (!cancelled) {
          setActive(booking)
        }
      })
      .catch((error: unknown) => console.warn('Could not load the active booking', error))
    return () => {
      cancelled = true
    }
  }, [userId, setActive])

  // Safety net for a missed `booking.expired` event: re-check shortly after the deadline.
  useEffect(() => {
    if (active === null) {
      return
    }
    const delay = Math.max(0, Date.parse(active.expires_at) - Date.now() + 3000)
    const timer = window.setTimeout(() => void refresh(), delay)
    return () => window.clearTimeout(timer)
  }, [active, refresh])

  const handleEvent = useCallback(
    (event: BookingEvent) => {
      setActive((current: Booking | null) => applyBookingEvent(current, event))
      const code = event.booking.scooter_code
      switch (event.type) {
        case 'booking.expiring':
          notify({
            kind: 'warning',
            text: `Бронь ${code} истекает через ${formatRemaining(event.seconds_left)}`,
          })
          break
        case 'booking.expired':
          notify({ kind: 'info', text: `Бронь ${code} истекла, самокат снова свободен` })
          break
        case 'booking.cancelled':
          notify({ kind: 'info', text: `Бронь ${code} отменена` })
          break
        case 'booking.created':
          break
      }
    },
    [notify, setActive],
  )

  const book = useCallback(
    async (scooterCode: string) => {
      if (userId === null) {
        return
      }
      setBusy(true)
      try {
        const booking = await createBooking(userId, scooterCode)
        setActive(booking)
        notify({
          kind: 'success',
          text: `Самокат ${scooterCode} забронирован до ${expiryTime(booking)}`,
        })
      } catch (error) {
        notify({ kind: 'error', text: describeError(error) })
      } finally {
        setBusy(false)
      }
    },
    [userId, notify, setActive],
  )

  const cancel = useCallback(async () => {
    if (userId === null || active === null) {
      return
    }
    setBusy(true)
    try {
      await cancelBooking(userId, active.id)
      setActive(null)
    } catch (error) {
      notify({ kind: 'error', text: describeError(error) })
      void refresh()
    } finally {
      setBusy(false)
    }
  }, [userId, active, notify, refresh, setActive])

  return { active, busy, book, cancel, handleEvent }
}
