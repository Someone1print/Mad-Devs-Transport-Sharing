import type { ZonePoint } from '../api/types'

function onSegment(p: ZonePoint, a: ZonePoint, b: ZonePoint): boolean {
  const cross = (b.lat - a.lat) * (p.lon - a.lon) - (b.lon - a.lon) * (p.lat - a.lat)
  if (Math.abs(cross) > 1e-12) {
    return false
  }
  return (
    Math.min(a.lat, b.lat) <= p.lat &&
    p.lat <= Math.max(a.lat, b.lat) &&
    Math.min(a.lon, b.lon) <= p.lon &&
    p.lon <= Math.max(a.lon, b.lon)
  )
}

/**
 * Even-odd ray casting on lat/lon as plane coordinates — the same algorithm as
 * backend/app/geo.py, used only to show "in zone / out of zone" before the user presses
 * Finish. The backend decides for real. Boundary points count as inside.
 */
export function pointInPolygon(point: ZonePoint, polygon: ZonePoint[]): boolean {
  const vertices = [...polygon]
  const first = vertices[0]
  const last = vertices[vertices.length - 1]
  if (vertices.length >= 2 && first.lat === last.lat && first.lon === last.lon) {
    vertices.pop()
  }
  if (vertices.length < 3) {
    return false
  }
  let inside = false
  for (let i = 0; i < vertices.length; i += 1) {
    const a = vertices[i]
    const b = vertices[(i + 1) % vertices.length]
    if (onSegment(point, a, b)) {
      return true
    }
    if (a.lon > point.lon !== b.lon > point.lon) {
      const latAtRay = a.lat + ((point.lon - a.lon) * (b.lat - a.lat)) / (b.lon - a.lon)
      if (point.lat < latAtRay) {
        inside = !inside
      }
    }
  }
  return inside
}
