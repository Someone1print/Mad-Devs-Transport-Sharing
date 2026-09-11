export type ScooterStatus = 'available' | 'reserved' | 'riding' | 'unavailable'

/** Scooter state as served by GET /api/scooters and pushed over the WebSocket. */
export interface Scooter {
  code: string
  lat: number
  lon: number
  battery: number
  status: ScooterStatus
  /** ISO 8601 timestamp of the last change on the server; used to drop stale updates. */
  updated_at: string
}

export interface User {
  id: number
  name: string
  created_at: string
}

export type BookingStatus = 'active' | 'cancelled' | 'expired'

export interface Booking {
  id: number
  scooter_code: string
  user_id: number
  status: BookingStatus
  created_at: string
  expires_at: string
}

export interface PublicConfig {
  booking_ttl_seconds: number
  booking_warn_before_seconds: number
  low_battery_threshold: number
}

export interface ScooterUpdatedEvent {
  type: 'scooter.updated'
  scooter: Scooter
}

export interface BookingCreatedEvent {
  type: 'booking.created'
  booking: Booking
}

export interface BookingCancelledEvent {
  type: 'booking.cancelled'
  booking: Booking
}

export interface BookingExpiringEvent {
  type: 'booking.expiring'
  booking: Booking
  seconds_left: number
}

export interface BookingExpiredEvent {
  type: 'booking.expired'
  booking: Booking
}

export type BookingEvent =
  | BookingCreatedEvent
  | BookingCancelledEvent
  | BookingExpiringEvent
  | BookingExpiredEvent

export type RealtimeEvent = ScooterUpdatedEvent | BookingEvent

export function isBookingEvent(event: RealtimeEvent): event is BookingEvent {
  return event.type.startsWith('booking.')
}
