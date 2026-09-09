import type { ScooterStatus } from '../api/types'

export interface StatusMeta {
  label: string
  color: string
}

export const STATUS_META: Record<ScooterStatus, StatusMeta> = {
  available: { label: 'Свободен', color: '#16a34a' },
  reserved: { label: 'Забронирован', color: '#f59e0b' },
  riding: { label: 'В поездке', color: '#2563eb' },
  unavailable: { label: 'Недоступен', color: '#6b7280' },
}

/** Order used by the legend. */
export const STATUS_ORDER: readonly ScooterStatus[] = [
  'available',
  'reserved',
  'riding',
  'unavailable',
]
