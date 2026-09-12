export type ScooterStatus = 'available' | 'reserved' | 'riding' | 'unavailable'

/** Scooter state as served by GET /api/scooters and pushed over the WebSocket. */
export interface Scooter {
  code: string
  lat: number
  lon: number
  battery: number
  status: ScooterStatus
  /** A ride on this scooter is paused (it stands still). */
  paused: boolean
  /** ISO 8601 timestamp of the last change on the server; used to drop stale updates. */
  updated_at: string
}

export interface User {
  id: number
  name: string
  created_at: string
}

export type BookingStatus = 'active' | 'cancelled' | 'expired' | 'used'

export interface Booking {
  id: number
  scooter_code: string
  user_id: number
  status: BookingStatus
  created_at: string
  expires_at: string
}

export type RideStatus = 'active' | 'paused' | 'finished'
export type SegmentKind = 'ride' | 'pause'

/** Money travels as decimal strings ("7.50"); the client keeps it in integer kopecks. */
export type Money = string

export interface RideSegment {
  kind: SegmentKind
  started_at: string
  ended_at: string | null
  seconds: number | null
  cost: Money | null
}

export interface Receipt {
  ride_seconds: number
  pause_seconds: number
  ride_cost: Money
  pause_cost: Money
  total_cost: Money
  currency: string
}

export interface Ride {
  id: number
  scooter_code: string
  user_id: number
  status: RideStatus
  started_at: string
  finished_at: string | null
  ride_rate_per_minute: Money
  pause_rate_per_minute: Money
  segments: RideSegment[]
  receipt: Receipt | null
}

export interface ZonePoint {
  lat: number
  lon: number
}

export interface Zone {
  id: number
  name: string
  points: ZonePoint[]
}

export interface PublicConfig {
  booking_ttl_seconds: number
  booking_warn_before_seconds: number
  low_battery_threshold: number
  ride_rate_per_minute: Money
  pause_rate_per_minute: Money
  currency: string
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

export interface RideEvent {
  type: 'ride.started' | 'ride.paused' | 'ride.resumed' | 'ride.finished'
  ride: Ride
}

export type RealtimeEvent = ScooterUpdatedEvent | BookingEvent | RideEvent

export function isBookingEvent(event: RealtimeEvent): event is BookingEvent {
  return event.type.startsWith('booking.')
}

export function isRideEvent(event: RealtimeEvent): event is RideEvent {
  return event.type.startsWith('ride.')
}
