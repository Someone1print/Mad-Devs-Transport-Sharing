import { useEffect, useRef, useState } from 'react'

import { fetchScooters, realtimeUrl } from '../api/scooters'
import {
  isBookingEvent,
  isRideEvent,
  type BookingEvent,
  type Email,
  type RealtimeEvent,
  type RideEvent,
} from '../api/types'
import { applyScooter, applyScooters, emptyStore, type ScooterStore } from './scooterStore'

export type ConnectionState = 'connecting' | 'live' | 'reconnecting'

export interface ScooterFeed {
  scooters: ScooterStore
  connection: ConnectionState
}

interface FeedOptions {
  /** The signed-in user: the socket is reopened when it changes, because the server binds a
   * socket to a user by the session cookie at the handshake (sign-in and sign-out change it). */
  userId: number | null
  onBookingEvent?: (event: BookingEvent) => void
  onRideEvent?: (event: RideEvent) => void
  onEmail?: (email: Email) => void
  /** Called after every reconnect (not the first connection): personal state may be stale. */
  onReconnect?: () => void
}

const MAX_RECONNECT_DELAY_MS = 15_000

/**
 * Keeps the fleet in sync with the server: opens the WebSocket first, then loads the full
 * list, so nothing published in between is lost (stale data is dropped by `updated_at`).
 * Reconnects with exponential backoff and reloads the list after every reconnect. The
 * browser's session cookie travels with the handshake, so personal events need no extra step.
 */
export function useScooterFeed(options: FeedOptions): ScooterFeed {
  const { userId, onBookingEvent, onRideEvent, onEmail, onReconnect } = options
  const [scooters, setScooters] = useState<ScooterStore>(emptyStore)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const onBookingEventRef = useRef(onBookingEvent)
  const onRideEventRef = useRef(onRideEvent)
  const onEmailRef = useRef(onEmail)
  const onReconnectRef = useRef(onReconnect)
  useEffect(() => {
    onBookingEventRef.current = onBookingEvent
    onRideEventRef.current = onRideEvent
    onEmailRef.current = onEmail
    onReconnectRef.current = onReconnect
  }, [onBookingEvent, onRideEvent, onEmail, onReconnect])

  useEffect(() => {
    let disposed = false
    let attempt = 0
    let reconnectTimer: number | undefined
    let connections = 0

    const loadSnapshot = async () => {
      try {
        const list = await fetchScooters()
        if (!disposed) {
          setScooters((store) => applyScooters(store, list))
        }
      } catch (error) {
        console.warn('Failed to load scooters, will retry after reconnect', error)
      }
    }

    const connect = () => {
      const socket = new WebSocket(realtimeUrl())
      socketRef.current = socket
      socket.onopen = () => {
        attempt = 0
        connections += 1
        setConnection('live')
        void loadSnapshot()
        if (connections > 1) {
          onReconnectRef.current?.()
        }
      }
      socket.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as RealtimeEvent
        if (event.type === 'scooter.updated') {
          setScooters((store) => applyScooter(store, event.scooter))
        } else if (isBookingEvent(event)) {
          onBookingEventRef.current?.(event)
        } else if (isRideEvent(event)) {
          onRideEventRef.current?.(event)
        } else if (event.type === 'email.sent') {
          onEmailRef.current?.(event.email)
        }
      }
      socket.onerror = () => socket.close()
      socket.onclose = () => {
        if (disposed) {
          return
        }
        setConnection('reconnecting')
        const delay = Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS)
        attempt += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer)
      socketRef.current?.close()
    }
  }, [userId])

  return { scooters, connection }
}
