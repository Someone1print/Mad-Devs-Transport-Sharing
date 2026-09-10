import type { Scooter } from './types'

export async function fetchScooters(signal?: AbortSignal): Promise<Scooter[]> {
  const response = await fetch('/api/scooters', { signal })
  if (!response.ok) {
    throw new Error(`GET /api/scooters failed with ${response.status}`)
  }
  return (await response.json()) as Scooter[]
}

/** WebSocket endpoint on the same origin as the page (nginx or the Vite proxy forward it). */
export function realtimeUrl(location: Location = window.location): string {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${location.host}/api/ws`
}
