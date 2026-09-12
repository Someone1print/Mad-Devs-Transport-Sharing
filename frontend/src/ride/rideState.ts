import type { Ride, RideEvent } from '../api/types'

/** Fold a personal ride event into the ride in progress (or just finished). */
export function applyRideEvent(current: Ride | null, event: RideEvent): Ride | null {
  if (event.type === 'ride.started') {
    return event.ride
  }
  if (current !== null && current.id !== event.ride.id) {
    return current
  }
  return event.ride
}

const MESSAGES: Record<string, string> = {
  outside_service_zone: 'Вы вне зоны обслуживания — вернитесь в зону, чтобы завершить поездку',
  booking_not_active: 'Бронь уже не активна, забронируйте самокат заново',
  booking_used: 'По этой брони поездка уже была',
  user_has_active_ride: 'У вас уже есть поездка — сначала завершите её',
  scooter_not_available: 'Самокат сейчас недоступен',
  ride_finished: 'Поездка уже завершена',
  not_your_ride: 'Это поездка другого пользователя',
  not_your_booking: 'Это бронь другого пользователя',
  ride_not_found: 'Поездка не найдена',
  booking_not_found: 'Бронь не найдена',
  user_required: 'Сессия устарела, введите имя заново',
  network: 'Нет связи с сервером, попробуйте ещё раз',
}

export function rideErrorMessage(code: string, serverMessage?: string): string {
  return MESSAGES[code] ?? serverMessage ?? 'Не удалось выполнить запрос, попробуйте ещё раз'
}

export function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes} мин ${String(rest).padStart(2, '0')} с`
}
