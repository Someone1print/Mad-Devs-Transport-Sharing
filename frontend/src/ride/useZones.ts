import { useEffect, useState } from 'react'

import { fetchZones } from '../api/rides'
import type { Zone, ZonePoint } from '../api/types'
import { pointInPolygon } from './geo'

/** Service zones from the backend; the polygon is static, so one load per page is enough. */
export function useZones(): Zone[] {
  const [zones, setZones] = useState<Zone[]>([])
  useEffect(() => {
    let cancelled = false
    fetchZones()
      .then((loaded) => {
        if (!cancelled) {
          setZones(loaded)
        }
      })
      .catch((error: unknown) => console.warn('Could not load service zones', error))
    return () => {
      cancelled = true
    }
  }, [])
  return zones
}

export function insideAnyZone(point: ZonePoint, zones: Zone[]): boolean {
  return zones.some((zone) => pointInPolygon(point, zone.points))
}
