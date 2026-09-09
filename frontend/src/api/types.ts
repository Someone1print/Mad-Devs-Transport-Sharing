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

export interface ScooterUpdatedEvent {
  type: 'scooter.updated'
  scooter: Scooter
}

export type RealtimeEvent = ScooterUpdatedEvent
