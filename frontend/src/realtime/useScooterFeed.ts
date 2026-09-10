import { useEffect, useState } from 'react'

import { fetchScooters, realtimeUrl } from '../api/scooters'
import type { RealtimeEvent } from '../api/types'
import { applyScooter, applyScooters, emptyStore, type ScooterStore } from './scooterStore'

export type ConnectionState = 'connecting' | 'live' | 'reconnecting'

export interface ScooterFeed {
  scooters: ScooterStore
  connection: ConnectionState
}

const MAX_RECONNECT_DELAY_MS = 15_000

/**
 * Keeps the fleet in sync with the server: opens the WebSocket first, then loads the full
 * list, so nothing published in between is lost (stale data is dropped by `updated_at`).
 * Reconnects with exponential backoff and reloads the list after every reconnect.
 */
export function useScooterFeed(): ScooterFeed {
  const [scooters, setScooters] = useState<ScooterStore>(emptyStore)
  const [connection, setConnection] = useState<ConnectionState>('connecting')

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
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
      socket = new WebSocket(realtimeUrl())
      socket.onopen = () => {
        attempt = 0
        setConnection('live')
        void loadSnapshot()
      }
      socket.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as RealtimeEvent
        if (event.type === 'scooter.updated') {
          setScooters((store) => applyScooter(store, event.scooter))
        }
      }
      socket.onerror = () => socket?.close()
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
      socket?.close()
    }
  }, [])

  return { scooters, connection }
}
