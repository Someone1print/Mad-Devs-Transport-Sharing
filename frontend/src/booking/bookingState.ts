import type { Booking, BookingEvent } from '../api/types'

/** Fold a personal booking event into the user's active booking. */
export function applyBookingEvent(active: Booking | null, event: BookingEvent): Booking | null {
  switch (event.type) {
    case 'booking.created':
      return event.booking
    case 'booking.cancelled':
    case 'booking.expired':
      return active !== null && active.id === event.booking.id ? null : active
    case 'booking.expiring':
      return active
  }
}

/** Seconds until the booking expires according to the client clock, never negative. */
export function remainingSeconds(booking: Booking, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(booking.expires_at) - now) / 1000))
}

/**
 * Seconds before expiry at which the "expiring soon" warning applies. Mirrors the backend:
 * the configured window, but never earlier than half of the booking's own length.
 */
export function warningWindowSeconds(booking: Booking, warnBeforeSeconds: number): number {
  const length = (Date.parse(booking.expires_at) - Date.parse(booking.created_at)) / 1000
  return Math.min(warnBeforeSeconds, Math.floor(length / 2))
}

export function formatRemaining(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

const MESSAGES: Record<string, string> = {
  scooter_not_available: 'Самокат уже забронирован другим пользователем',
  user_has_active_booking: 'У вас уже есть активная бронь',
  scooter_not_found: 'Самокат не найден',
  booking_not_active: 'Бронь уже завершена',
  booking_not_found: 'Бронь не найдена',
  not_your_booking: 'Это бронь другого пользователя',
  user_required: 'Сессия устарела, введите имя заново',
  network: 'Нет связи с сервером, попробуйте ещё раз',
}

/** Human text for an API error code; falls back to the server message, then to a generic one. */
export function bookingErrorMessage(code: string, serverMessage?: string): string {
  return MESSAGES[code] ?? serverMessage ?? 'Не удалось выполнить запрос, попробуйте ещё раз'
}
