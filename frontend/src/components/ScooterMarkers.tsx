import { CircleMarker, Popup } from 'react-leaflet'

import type { Scooter } from '../api/types'
import { STATUS_META } from '../config/status'

interface ScooterMarkersProps {
  scooters: Iterable<Scooter>
}

/** One circle per scooter, coloured by status; react-leaflet moves it when `center` changes. */
export function ScooterMarkers({ scooters }: ScooterMarkersProps) {
  return (
    <>
      {Array.from(scooters, (scooter) => {
        const meta = STATUS_META[scooter.status]
        return (
          <CircleMarker
            key={scooter.code}
            center={[scooter.lat, scooter.lon]}
            radius={9}
            pathOptions={{ color: '#ffffff', weight: 2, fillColor: meta.color, fillOpacity: 0.95 }}
          >
            <Popup>
              <div className="scooter-popup">
                <strong>{scooter.code}</strong>
                <div>Заряд: {scooter.battery}%</div>
                <div>
                  Статус: <span style={{ color: meta.color }}>{meta.label}</span>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}
