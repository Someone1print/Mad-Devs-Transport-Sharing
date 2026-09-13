import { useEffect, useRef, type KeyboardEvent, type MouseEvent } from 'react'

import { displayMoney } from '../account/mailbox'
import type { LoadStatus } from '../account/useRideHistory'
import type { Email, Ride, User } from '../api/types'
import { formatMoney, liveEstimate } from '../ride/billing'
import { formatDuration } from '../ride/rideState'

export type AccountTab = 'rides' | 'mail'

interface AccountPanelProps {
  user: User
  activeRide: Ride | null
  history: Ride[]
  historyStatus: LoadStatus
  emails: Email[]
  mailStatus: LoadStatus
  currency: string
  now: number
  tab: AccountTab
  onTabChange: (tab: AccountTab) => void
  onOpenMail: () => void
  onRetryHistory: () => void
  onRetryMail: () => void
  onClose: () => void
}

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

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

function LoadFailed({ what, onRetry }: { what: string; onRetry: () => void }) {
  return (
    <p className="account__empty account__error" role="alert">
      Не удалось загрузить {what}.{' '}
      <button type="button" className="link" onClick={onRetry}>
        Повторить
      </button>
    </p>
  )
}

/** The rider's account: current ride, finished rides with receipts, and the mailbox. */
export function AccountPanel(props: AccountPanelProps) {
  const { user, activeRide, history, historyStatus, emails, mailStatus, currency, now } = props
  const { tab, onTabChange, onOpenMail, onRetryHistory, onRetryMail, onClose } = props
  const panelRef = useRef<HTMLDivElement>(null)

  // a dialog takes the focus and gives it back: keyboard users land inside, not on the map behind
  useEffect(() => {
    const opener = document.activeElement
    panelRef.current?.focus()
    return () => {
      if (opener instanceof HTMLElement) {
        opener.focus()
      }
    }
  }, [])

  useEffect(() => {
    if (tab === 'mail') {
      onOpenMail()
    }
  }, [tab, onOpenMail, emails.length])

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab' || !panelRef.current) {
      return
    }
    // keep Tab inside the dialog: the page behind is inert for the mouse, so also for the keyboard
    const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (focusable.length === 0) {
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const onBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  const estimate = activeRide ? liveEstimate(activeRide, now) : null

  return (
    <div className="modal modal--right" onClick={onBackdropClick}>
      <div
        className="account"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-title"
        tabIndex={-1}
        ref={panelRef}
        onKeyDown={onKeyDown}
        data-testid="account"
      >
        <div className="account__top">
          <header className="account__header">
            <h2 id="account-title" className="account__title">
              Кабинет
            </h2>
            <span className="account__who">
              {user.name}
              {emails[0] ? ` · ${emails[0].to_address}` : ''}
            </span>
            <button type="button" className="account__close" aria-label="Закрыть" onClick={onClose}>
              ×
            </button>
          </header>
          <div className="tabs" role="tablist" aria-label="Разделы кабинета">
            <button
              type="button"
              role="tab"
              id="account-tab-rides"
              aria-selected={tab === 'rides'}
              aria-controls="account-panel-rides"
              className={`tabs__tab ${tab === 'rides' ? 'tabs__tab--active' : ''}`}
              onClick={() => onTabChange('rides')}
            >
              Поездки
            </button>
            <button
              type="button"
              role="tab"
              id="account-tab-mail"
              aria-selected={tab === 'mail'}
              aria-controls="account-panel-mail"
              className={`tabs__tab ${tab === 'mail' ? 'tabs__tab--active' : ''}`}
              onClick={() => onTabChange('mail')}
              data-testid="tab-mail"
            >
              Почта{emails.length > 0 ? ` (${emails.length})` : ''}
            </button>
          </div>
        </div>

        {tab === 'rides' && (
          <section
            className="account__section"
            role="tabpanel"
            id="account-panel-rides"
            aria-labelledby="account-tab-rides"
            data-testid="rides-tab"
          >
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
            {historyStatus === 'error' && history.length === 0 ? (
              <LoadFailed what="историю поездок" onRetry={onRetryHistory} />
            ) : history.length === 0 ? (
              <p className="account__empty">
                {historyStatus === 'loading' ? 'Загружаем…' : 'Завершённых поездок пока нет.'}
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
          <section
            className="account__section"
            role="tabpanel"
            id="account-panel-mail"
            aria-labelledby="account-tab-mail"
            data-testid="mail-tab"
          >
            {mailStatus === 'error' && emails.length === 0 ? (
              <LoadFailed what="почту" onRetry={onRetryMail} />
            ) : emails.length === 0 ? (
              <p className="account__empty">
                {mailStatus === 'loading' ? 'Загружаем…' : 'Писем пока нет. Чек за поездку придёт сюда.'}
              </p>
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
