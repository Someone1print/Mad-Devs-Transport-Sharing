import { Polygon, Tooltip } from 'react-leaflet'

import type { Zone } from '../api/types'

interface ZoneLayerProps {
  zones: Zone[]
}

/** Service zone boundaries: rides can only be finished inside. */
export function ZoneLayer({ zones }: ZoneLayerProps) {
  return (
    <>
      {zones.map((zone) => (
        <Polygon
          key={zone.id}
          positions={zone.points.map((p) => [p.lat, p.lon] as [number, number])}
          className={`service-zone service-zone-${zone.id}`}
          pathOptions={{
            color: '#2563eb',
            weight: 2,
            dashArray: '6 6',
            fillColor: '#3b82f6',
            fillOpacity: 0.06,
            interactive: false,
          }}
        >
          <Tooltip sticky>Зона обслуживания: {zone.name}</Tooltip>
        </Polygon>
      ))}
    </>
  )
}
