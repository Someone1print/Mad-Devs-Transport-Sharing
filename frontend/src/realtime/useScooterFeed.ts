import { useEffect, useRef, useState } from 'react'

import { fetchScooters, realtimeUrl } from '../api/scooters'
import { isBookingEvent, type BookingEvent, type RealtimeEvent } from '../api/types'
import { applyScooter, applyScooters, emptyStore, type ScooterStore } from './scooterStore'

export type ConnectionState = 'connecting' | 'live' | 'reconnecting'

export interface ScooterFeed {
  scooters: ScooterStore
  connection: ConnectionState
}

interface FeedOptions {
  /** Once known, the socket identifies itself so personal booking events can be delivered. */
  userId: number | null
  onBookingEvent?: (event: BookingEvent) => void
}

const MAX_RECONNECT_DELAY_MS = 15_000

function identify(socket: WebSocket | null, userId: number | null): void {
  if (socket !== null && socket.readyState === WebSocket.OPEN && userId !== null) {
    socket.send(JSON.stringify({ type: 'identify', user_id: userId }))
  }
}

/**
 * Keeps the fleet in sync with the server: opens the WebSocket first, then loads the full
 * list, so nothing published in between is lost (stale data is dropped by `updated_at`).
 * Reconnects with exponential backoff and reloads the list after every reconnect.
 */
export function useScooterFeed({ userId, onBookingEvent }: FeedOptions): ScooterFeed {
  const [scooters, setScooters] = useState<ScooterStore>(emptyStore)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const userIdRef = useRef(userId)
  const onBookingEventRef = useRef(onBookingEvent)
  useEffect(() => {
    userIdRef.current = userId
    onBookingEventRef.current = onBookingEvent
  }, [userId, onBookingEvent])

  useEffect(() => {
    let disposed = false
    let attempt = 0
    let reconnectTimer: number | undefined

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
        setConnection('live')
        identify(socket, userIdRef.current)
        void loadSnapshot()
      }
      socket.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as RealtimeEvent
        if (event.type === 'scooter.updated') {
          setScooters((store) => applyScooter(store, event.scooter))
        } else if (isBookingEvent(event)) {
          onBookingEventRef.current?.(event)
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
  }, [])

  // the rider may register after the socket opened: identify as soon as the id is known
  useEffect(() => {
    identify(socketRef.current, userId)
  }, [userId])

  return { scooters, connection }
}
