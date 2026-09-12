import { useEffect, useState } from 'react'

import { displayMoney } from '../account/mailbox'
import type { Email, Ride, User } from '../api/types'
import { formatMoney, liveEstimate } from '../ride/billing'
import { formatDuration } from '../ride/rideState'

export type AccountTab = 'rides' | 'mail'

interface AccountPanelProps {
  user: User
  activeRide: Ride | null
  history: Ride[]
  historyLoading: boolean
  emails: Email[]
  currency: string
  now: number
  initialTab: AccountTab
  onOpenMail: () => void
  onClose: () => void
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Rows of a finished ride: the stored receipt, shown verbatim (no client arithmetic). */
function ReceiptRows({ ride, currency }: { ride: Ride; currency: string }) {
  const receipt = ride.receipt
  if (!receipt) {
    return null
  }
  return (
    <dl className="history__receipt">
      <div>
        <dt>Ехали</dt>
        <dd>
          {formatDuration(receipt.ride_seconds)} · {displayMoney(receipt.ride_cost, currency)}
        </dd>
      </div>
      <div>
        <dt>Стояли</dt>
        <dd>
          {formatDuration(receipt.pause_seconds)} · {displayMoney(receipt.pause_cost, currency)}
        </dd>
      </div>
      <div className="history__total">
        <dt>Итого</dt>
        <dd data-testid="history-total">{displayMoney(receipt.total_cost, currency)}</dd>
      </div>
    </dl>
  )
}

/** The rider's account: current ride, finished rides with receipts, and the mailbox. */
export function AccountPanel(props: AccountPanelProps) {
  const { user, activeRide, history, historyLoading, emails, currency, now } = props
  const { initialTab, onOpenMail, onClose } = props
  const [tab, setTab] = useState<AccountTab>(initialTab)

  useEffect(() => {
    if (tab === 'mail') {
      onOpenMail()
    }
  }, [tab, onOpenMail, emails.length])

  const estimate = activeRide ? liveEstimate(activeRide, now) : null

  return (
    <div className="modal modal--right" role="dialog" aria-modal="true" aria-labelledby="account-title">
      <div className="account" data-testid="account">
        <header className="account__header">
          <h2 id="account-title" className="account__title">
            {user.name}
          </h2>
          <span className="account__address">{emails[0]?.to_address ?? ''}</span>
          <button type="button" className="toast__close" aria-label="Закрыть" onClick={onClose}>
            ×
          </button>
        </header>
        <nav className="tabs" aria-label="Разделы кабинета">
          <button
            type="button"
            className={`tabs__tab ${tab === 'rides' ? 'tabs__tab--active' : ''}`}
            onClick={() => setTab('rides')}
          >
            Поездки
          </button>
          <button
            type="button"
            className={`tabs__tab ${tab === 'mail' ? 'tabs__tab--active' : ''}`}
            onClick={() => setTab('mail')}
            data-testid="tab-mail"
          >
            Почта{emails.length > 0 ? ` (${emails.length})` : ''}
          </button>
        </nav>

        {tab === 'rides' && (
          <section className="account__section" data-testid="rides-tab">
            <h3 className="account__heading">Текущая поездка</h3>
            {activeRide && estimate ? (
              <div className="history__item history__item--current" data-testid="current-ride">
                <div className="history__row">
                  <strong>{activeRide.scooter_code}</strong>
                  <span className="history__meta">
                    {activeRide.status === 'paused' ? 'на паузе' : 'едет'} · с{' '}
                    {formatWhen(activeRide.started_at)}
                  </span>
                </div>
                <div className="history__estimate">
                  Сейчас примерно {formatMoney(estimate.totalKopecks)} {currency} — оценка, точный
                  счёт выставит сервер при завершении
                </div>
              </div>
            ) : (
              <p className="account__empty">Сейчас вы никуда не едете.</p>
            )}

            <h3 className="account__heading">История поездок</h3>
            {history.length === 0 ? (
              <p className="account__empty">
                {historyLoading ? 'Загружаем…' : 'Завершённых поездок пока нет.'}
              </p>
            ) : (
              <ul className="history" data-testid="history">
                {history.map((ride) => (
                  <li key={ride.id} className="history__item" data-testid="history-item">
                    <div className="history__row">
                      <strong>{ride.scooter_code}</strong>
                      <span className="history__meta">
                        {formatWhen(ride.started_at)}
                        {ride.finished_at ? ` — ${formatWhen(ride.finished_at)}` : ''}
                      </span>
                    </div>
                    <ReceiptRows ride={ride} currency={currency} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {tab === 'mail' && (
          <section className="account__section" data-testid="mail-tab">
            {emails.length === 0 ? (
              <p className="account__empty">Писем пока нет. Чек за поездку придёт сюда.</p>
            ) : (
              <ul className="mail" data-testid="mail-list">
                {emails.map((email) => (
                  <li key={email.id} className="mail__item" data-testid="mail-item">
                    <div className="history__row">
                      <strong>{email.subject}</strong>
                      <span className="history__meta">{formatWhen(email.created_at)}</span>
                    </div>
                    <div className="mail__to">Кому: {email.to_address}</div>
                    <pre className="mail__body">{email.body}</pre>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
