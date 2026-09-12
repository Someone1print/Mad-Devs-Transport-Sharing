import type { Booking } from '../api/types'
import { formatRemaining, remainingSeconds } from '../booking/bookingState'

interface MyBookingProps {
  booking: Booking
  now: number
  busy: boolean
  onStart: () => void
  onCancel: () => void
}

/** Header widget: the rider's current hold with a countdown, start-ride and cancel buttons. */
export function MyBooking({ booking, now, busy, onStart, onCancel }: MyBookingProps) {
  const left = remainingSeconds(booking, now)
  return (
    <div className="my-booking" data-testid="my-booking">
      <span className="my-booking__label">Моя бронь</span>
      <strong>{booking.scooter_code}</strong>
      <span className="my-booking__timer" aria-label="Осталось времени">
        {formatRemaining(left)}
      </span>
      <button type="button" className="btn btn--primary" disabled={busy} onClick={onStart}>
        Начать поездку
      </button>
      <button type="button" className="btn btn--ghost" disabled={busy} onClick={onCancel}>
        Отменить
      </button>
    </div>
  )
}
