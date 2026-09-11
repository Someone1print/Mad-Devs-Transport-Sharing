import { useEffect, useState } from 'react'

import { request } from './client'
import type { PublicConfig } from './types'

/** Used until GET /api/config answers (and if it never does). Mirrors the backend defaults. */
export const DEFAULT_CONFIG: PublicConfig = {
  booking_ttl_seconds: 900,
  booking_warn_before_seconds: 180,
  low_battery_threshold: 15,
}

export function fetchConfig(): Promise<PublicConfig> {
  return request<PublicConfig>('/api/config')
}

export function usePublicConfig(): PublicConfig {
  const [config, setConfig] = useState<PublicConfig>(DEFAULT_CONFIG)
  useEffect(() => {
    let cancelled = false
    fetchConfig()
      .then((loaded) => {
        if (!cancelled) {
          setConfig(loaded)
        }
      })
      .catch((error: unknown) => console.warn('Using default config', error))
    return () => {
      cancelled = true
    }
  }, [])
  return config
}
