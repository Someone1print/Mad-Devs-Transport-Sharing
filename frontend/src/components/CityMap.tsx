import type { ReactNode } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import { BISHKEK_CENTER, DEFAULT_ZOOM, OSM_ATTRIBUTION, OSM_TILE_URL } from '../config/map'

interface CityMapProps {
  children?: ReactNode
}

/** Full-size OpenStreetMap view centred on Bishkek; overlays (markers) come as children. */
export function CityMap({ children }: CityMapProps) {
  return (
    <MapContainer center={BISHKEK_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom className="city-map">
      <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
      {children}
    </MapContainer>
  )
}
