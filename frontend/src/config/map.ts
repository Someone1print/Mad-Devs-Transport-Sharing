import type { LatLngExpression } from 'leaflet'

/** Centre of the simulated area in Bishkek (Chuy avenue between Manas and Erkindik). */
export const BISHKEK_CENTER: LatLngExpression = [42.875, 74.6]

/** Zoom 14 shows the whole simulated area while individual movements stay visible. */
export const DEFAULT_ZOOM = 14

export const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
