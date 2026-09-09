import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import { BISHKEK_CENTER, DEFAULT_ZOOM, OSM_ATTRIBUTION, OSM_TILE_URL } from '../config/map'

/** Full-size OpenStreetMap view centred on Bishkek. Scooter markers will be layered on top later. */
export function CityMap() {
  return (
    <MapContainer center={BISHKEK_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom className="city-map">
      <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
    </MapContainer>
  )
}
