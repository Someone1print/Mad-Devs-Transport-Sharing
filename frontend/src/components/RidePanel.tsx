import type { Ride, Scooter, Zone } from '../api/types'
import { formatMoney, liveEstimate } from '../ride/billing'
import { formatDuration } from '../ride/rideState'
import { insideAnyZone } from '../ride/useZones'

interface RidePanelProps {
  ride: Ride
  scooter: Scooter | undefined
  zones: Zone[]
  now: number
  busy: boolean
  currency: string
  onPause: () => void
  onResume: () => void
  onFinish: () => void
}

/** Floating card for the ride in progress: timers, live cost, zone indicator and controls. */
export function RidePanel(props: RidePanelProps) {
  const { ride, scooter, zones, now, busy, currency, onPause, onResume, onFinish } = props
  const estimate = liveEstimate(ride, now)
  const paused = ride.status === 'paused'
  const inZone = scooter ? insideAnyZone({ lat: scooter.lat, lon: scooter.lon }, zones) : null
  const zoneKnown = zones.length > 0 && inZone !== null

  return (
    <section className="ride-panel" data-testid="ride-panel" aria-label="Текущая поездка">
      <header className="ride-panel__header">
        <span className={`ride-panel__state ride-panel__state--${ride.status}`}>
          {paused ? 'Пауза' : 'В поездке'}
        </span>
        <strong>{ride.scooter_code}</strong>
        {zoneKnown && (
          <span className={`zone-badge zone-badge--${inZone ? 'in' : 'out'}`} data-testid="zone-badge">
            {inZone ? 'В зоне обслуживания' : 'Вне зоны обслуживания'}
          </span>
        )}
      </header>
      <dl className="ride-panel__stats">
        <div>
          <dt>Езда</dt>
          <dd>
            {formatDuration(estimate.rideSeconds)} · {formatMoney(estimate.rideKopecks)}
          </dd>
        </div>
        <div>
          <dt>Пауза</dt>
          <dd>
            {formatDuration(estimate.pauseSeconds)} · {formatMoney(estimate.pauseKopecks)}
          </dd>
        </div>
        <div className="ride-panel__total">
          <dt>Сейчас</dt>
          <dd data-testid="ride-total">
            {formatMoney(estimate.totalKopecks)} {currency}
          </dd>
        </div>
      </dl>
      <div className="ride-panel__actions">
        {paused ? (
          <button type="button" className="btn btn--primary" disabled={busy} onClick={onResume}>
            Продолжить
          </button>
        ) : (
          <button type="button" className="btn btn--secondary" disabled={busy} onClick={onPause}>
            Пауза
          </button>
        )}
        <button
          type="button"
          className="btn btn--danger"
          disabled={busy}
          onClick={onFinish}
          title={inZone === false ? 'Завершить можно только внутри зоны обслуживания' : undefined}
        >
          Завершить
        </button>
      </div>
      {inZone === false && (
        <p className="ride-panel__hint">
          Самокат вне зоны обслуживания — вернитесь внутрь границы, чтобы завершить поездку.
        </p>
      )}
    </section>
  )
}
