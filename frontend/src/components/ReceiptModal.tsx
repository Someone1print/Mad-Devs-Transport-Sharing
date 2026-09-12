import type { Ride } from '../api/types'
import { formatMoney, liveEstimate } from '../ride/billing'
import { formatDuration } from '../ride/rideState'

interface ReceiptModalProps {
  ride: Ride
  onClose: () => void
}

/** Final bill after a ride: how long the rider rode, how long they stood, what it cost. */
export function ReceiptModal({ ride, onClose }: ReceiptModalProps) {
  const receipt = ride.receipt
  // a finished ride carries its receipt, so the time argument is never used here
  const totals = liveEstimate(ride, 0)
  const currency = receipt?.currency ?? 'KGS'
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="receipt-title">
      <div className="modal__card" data-testid="receipt">
        <h2 id="receipt-title" className="modal__title">
          Поездка завершена
        </h2>
        <p className="modal__subtitle">Самокат {ride.scooter_code}</p>
        <table className="receipt">
          <tbody>
            <tr>
              <th scope="row">Ехали</th>
              <td>{formatDuration(totals.rideSeconds)}</td>
              <td className="receipt__money">
                {formatMoney(totals.rideKopecks)} {currency}
              </td>
            </tr>
            <tr>
              <th scope="row">Стояли</th>
              <td>{formatDuration(totals.pauseSeconds)}</td>
              <td className="receipt__money">
                {formatMoney(totals.pauseKopecks)} {currency}
              </td>
            </tr>
            <tr className="receipt__total">
              <th scope="row">Итого</th>
              <td />
              <td className="receipt__money" data-testid="receipt-total">
                {formatMoney(totals.totalKopecks)} {currency}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="modal__hint">
          Тариф: {ride.ride_rate_per_minute} {currency}/мин езды, {ride.pause_rate_per_minute}{' '}
          {currency}/мин паузы; оплата посекундная.
        </p>
        <button type="button" className="btn btn--primary" onClick={onClose} autoFocus>
          Понятно
        </button>
      </div>
    </div>
  )
}
