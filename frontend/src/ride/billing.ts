/**
 * Client-side mirror of backend/app/billing.py for the live cost display.
 *
 * Money is handled as integer kopecks; a segment costs
 * round(rateKopecks * seconds / 60). For integer inputs the exact value is a rational with
 * denominator 60, so it is either exactly k + 0.5 (representable, Math.round rounds it up like
 * the backend's ROUND_HALF_UP) or at least 1/60 away from a half — float error cannot flip the
 * rounding. The server's receipt is still the source of truth once a ride is finished.
 */

import type { Ride, RideSegment } from '../api/types'

export interface Estimate {
  rideSeconds: number
  pauseSeconds: number
  rideKopecks: number
  pauseKopecks: number
  totalKopecks: number
}

/** "7.50" → 750; "12" → 1200. Never a float in between. */
export function parseMoney(text: string): number {
  const [whole, fraction = ''] = text.trim().split('.')
  const cents = (fraction + '00').slice(0, 2)
  return Number(whole) * 100 + Number(cents)
}

/** 1419 → "14.19" */
export function formatMoney(kopecks: number): string {
  const sign = kopecks < 0 ? '-' : ''
  const abs = Math.abs(kopecks)
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

export function segmentCostKopecks(rateKopecks: number, seconds: number): number {
  return Math.round((rateKopecks * seconds) / 60)
}

/** Whole seconds between two instants, never negative. */
export function segmentSeconds(startMs: number, endMs: number): number {
  return Math.max(0, Math.floor((endMs - startMs) / 1000))
}

function closedSeconds(segment: RideSegment, now: number): number {
  if (segment.seconds !== null) {
    return segment.seconds
  }
  return segmentSeconds(Date.parse(segment.started_at), now)
}

/** Current cost of a ride: closed segments as billed by the server plus the open one live. */
export function liveEstimate(ride: Ride, now: number): Estimate {
  if (ride.receipt) {
    return {
      rideSeconds: ride.receipt.ride_seconds,
      pauseSeconds: ride.receipt.pause_seconds,
      rideKopecks: parseMoney(ride.receipt.ride_cost),
      pauseKopecks: parseMoney(ride.receipt.pause_cost),
      totalKopecks: parseMoney(ride.receipt.total_cost),
    }
  }
  const rideRate = parseMoney(ride.ride_rate_per_minute)
  const pauseRate = parseMoney(ride.pause_rate_per_minute)
  const estimate: Estimate = {
    rideSeconds: 0,
    pauseSeconds: 0,
    rideKopecks: 0,
    pauseKopecks: 0,
    totalKopecks: 0,
  }
  for (const segment of ride.segments) {
    const seconds = closedSeconds(segment, now)
    const rate = segment.kind === 'ride' ? rideRate : pauseRate
    const cost = segment.cost !== null ? parseMoney(segment.cost) : segmentCostKopecks(rate, seconds)
    if (segment.kind === 'ride') {
      estimate.rideSeconds += seconds
      estimate.rideKopecks += cost
    } else {
      estimate.pauseSeconds += seconds
      estimate.pauseKopecks += cost
    }
  }
  estimate.totalKopecks = estimate.rideKopecks + estimate.pauseKopecks
  return estimate
}
