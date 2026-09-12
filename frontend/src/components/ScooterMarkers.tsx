import { CircleMarker, Popup } from 'react-leaflet'

import type { Booking, Scooter } from '../api/types'
import { formatRemaining, remainingSeconds } from '../booking/bookingState'
import { STATUS_META } from '../config/status'

interface ScooterMarkersProps {
  scooters: Iterable<Scooter>
  myBooking: Booking | null
  /** Code of the scooter the rider is currently riding, if any. */
  myRideCode: string | null
  now: number
  canBook: boolean
  busy: boolean
  ttlMinutes: number
  onBook: (scooterCode: string) => void
  onCancel: () => void
  onStart: () => void
}

interface PopupActionsProps extends Omit<ScooterMarkersProps, 'scooters'> {
  scooter: Scooter
}

function PopupActions(props: PopupActionsProps) {
  const { scooter, myBooking, myRideCode, now, canBook, busy, ttlMinutes, onBook, onCancel, onStart } =
    props
  const mine = myBooking !== null && myBooking.scooter_code === scooter.code

  if (myRideCode === scooter.code) {
    return (
      <div className="popup-actions__note">
        {scooter.paused ? 'Ваша поездка · пауза' : 'Ваша поездка'} — управление в панели слева
      </div>
    )
  }

  if (mine && myBooking) {
    return (
      <div className="popup-actions">
        <div className="popup-actions__note">
          Ваша бронь · осталось {formatRemaining(remainingSeconds(myBooking, now))}
        </div>
        <button type="button" className="btn btn--primary" disabled={busy} onClick={onStart}>
          Начать поездку
        </button>
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={onCancel}>
          Отменить бронь
        </button>
      </div>
    )
  }
  if (scooter.status === 'available') {
    const blocked = !canBook || myBooking !== null
    return (
      <div className="popup-actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={blocked || busy}
          onClick={() => onBook(scooter.code)}
        >
          Забронировать на {ttlMinutes} мин
        </button>
        {myBooking !== null && (
          <div className="popup-actions__note">Сначала отмените текущую бронь</div>
        )}
        {myRideCode !== null && (
          <div className="popup-actions__note">Сначала завершите поездку</div>
        )}
      </div>
    )
  }
  if (scooter.status === 'reserved') {
    return <div className="popup-actions__note">Забронирован другим пользователем</div>
  }
  if (scooter.status === 'riding') {
    return (
      <div className="popup-actions__note">
        {scooter.paused ? 'В поездке · пауза' : 'В поездке'}
      </div>
    )
  }
  return null
}

/** One circle per scooter, coloured by status; react-leaflet moves it when `center` changes. */
export function ScooterMarkers({ scooters, ...rest }: ScooterMarkersProps) {
  return (
    <>
      {Array.from(scooters, (scooter) => {
        const meta = STATUS_META[scooter.status]
        const mine =
          (rest.myBooking !== null && rest.myBooking.scooter_code === scooter.code) ||
          rest.myRideCode === scooter.code
        return (
          <CircleMarker
            key={scooter.code}
            center={[scooter.lat, scooter.lon]}
            radius={mine ? 11 : 9}
            // className must be a constructor option: Leaflet only adds it when the path is created
            className={`scooter scooter-${scooter.code}`}
            pathOptions={{
              color: mine ? '#0f172a' : '#ffffff',
              weight: mine ? 3 : 2,
              fillColor: meta.color,
              fillOpacity: 0.95,
            }}
          >
            <Popup>
              <div className="scooter-popup">
                <strong>{scooter.code}</strong>
                <div>Заряд: {scooter.battery}%</div>
                <div>
                  Статус: <span style={{ color: meta.color }}>{meta.label}</span>
                </div>
                <PopupActions scooter={scooter} {...rest} />
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}
