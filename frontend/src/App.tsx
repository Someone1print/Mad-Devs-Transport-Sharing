import { useCallback, useState } from 'react'

import { useMailbox } from './account/useMailbox'
import { useRideHistory } from './account/useRideHistory'

import { usePublicConfig } from './api/config'
import type { RideEvent } from './api/types'
import { formatRemaining, remainingSeconds, warningWindowSeconds } from './booking/bookingState'
import { useBooking } from './booking/useBooking'
import { AccountPanel, type AccountTab } from './components/AccountPanel'
import { CityMap } from './components/CityMap'
import { MyBooking } from './components/MyBooking'
import { ReceiptModal } from './components/ReceiptModal'
import { RidePanel } from './components/RidePanel'
import { ScooterMarkers } from './components/ScooterMarkers'
import { ToastStack } from './components/Toasts'
import { UserGate } from './components/UserGate'
import { ZoneLayer } from './components/ZoneLayer'
import { STATUS_META, STATUS_ORDER } from './config/status'
import { useNow } from './hooks/useNow'
import { useToasts } from './hooks/useToasts'
import { useScooterFeed, type ConnectionState } from './realtime/useScooterFeed'
import { useRide } from './ride/useRide'
import { useZones } from './ride/useZones'
import { useCurrentUser } from './user/useCurrentUser'
import './App.css'

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: 'Подключение…',
  live: 'Онлайн',
  reconnecting: 'Переподключение…',
}

function App() {
  const now = useNow(1000)
  const config = usePublicConfig()
  const zones = useZones()
  const currentUser = useCurrentUser()
  const user = currentUser.state.status === 'ready' ? currentUser.state.user : null
  const userId = user?.id ?? null
  const { toasts, notify, dismiss } = useToasts()
  const booking = useBooking({ userId, notify })
  const ride = useRide({ userId, notify })
  const mailbox = useMailbox(userId)
  const [finishedCount, setFinishedCount] = useState(0)
  const history = useRideHistory(userId, finishedCount)
  const [account, setAccount] = useState<AccountTab | null>(null)
  const clearBooking = booking.clear
  const handleRideEvent = ride.handleEvent
  const onRideEvent = useCallback(
    (event: RideEvent) => {
      handleRideEvent(event)
      if (event.type === 'ride.started') {
        clearBooking() // the booking was converted into this ride
      }
      if (event.type === 'ride.finished') {
        setFinishedCount((n) => n + 1) // the history has a new entry
      }
    },
    [handleRideEvent, clearBooking],
  )
  const onEmail = mailbox.handleEvent
  const refreshRide = ride.refresh
  const refreshBooking = booking.refresh
  const refreshMail = mailbox.refresh
  const onReconnect = useCallback(() => {
    // events sent while the socket was down are gone: reload the personal state
    void refreshRide()
    void refreshBooking()
    void refreshMail()
  }, [refreshRide, refreshBooking, refreshMail])
  const { scooters, connection } = useScooterFeed({
    userId,
    onBookingEvent: booking.handleEvent,
    onRideEvent,
    onEmail,
    onReconnect,
  })

  const list = Array.from(scooters.values())
  const available = list.filter((scooter) => scooter.status === 'available').length
  const myBooking = ride.active === null ? booking.active : null
  const left = myBooking ? remainingSeconds(myBooking, now) : null
  const expiringSoon =
    myBooking !== null &&
    left !== null &&
    left <= warningWindowSeconds(myBooking, config.booking_warn_before_seconds)
  const busy = booking.busy || ride.busy

  const startRide = async () => {
    if (myBooking === null) {
      return
    }
    if (await ride.start(myBooking.id)) {
      booking.clear()
    }
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <h1 className="app__title">Transport Sharing</h1>
          <span className="app__subtitle">Аренда самокатов · Бишкек</span>
        </div>
        <ul className="legend" aria-label="Статусы самокатов">
          {STATUS_ORDER.map((status) => (
            <li key={status} className="legend__item">
              <span className="legend__dot" style={{ background: STATUS_META[status].color }} />
              {STATUS_META[status].label}
            </li>
          ))}
          <li className="legend__item">
            <span className="legend__zone" />
            Зона обслуживания
          </li>
        </ul>
        {myBooking && (
          <MyBooking
            booking={myBooking}
            now={now}
            busy={busy}
            onStart={() => void startRide()}
            onCancel={() => void booking.cancel()}
          />
        )}
        <div className="app__stats">
          <span>
            {list.length} самокатов · {available} свободны
          </span>
          {user && (
            <span className="app__user">
              <button
                type="button"
                className="btn btn--ghost btn--small"
                onClick={() => setAccount('rides')}
                data-testid="open-account"
              >
                Кабинет
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--small"
                onClick={() => setAccount('mail')}
                data-testid="open-mail"
              >
                Почта{mailbox.unread > 0 ? ` · ${mailbox.unread}` : ''}
              </button>
              {user.name}
              <button type="button" className="link" onClick={currentUser.signOut}>
                сменить
              </button>
            </span>
          )}
          <span className={`connection connection--${connection}`}>
            {CONNECTION_LABEL[connection]}
          </span>
        </div>
      </header>
      {expiringSoon && myBooking && left !== null && (
        <div className="banner" role="alert">
          Бронь {myBooking.scooter_code} истекает через {formatRemaining(left)}. Начните поездку,
          иначе самокат снова станет свободным.
        </div>
      )}
      <main className="app__map">
        <CityMap>
          <ZoneLayer zones={zones} />
          <ScooterMarkers
            scooters={list}
            myBooking={myBooking}
            myRideCode={ride.active?.scooter_code ?? null}
            now={now}
            canBook={user !== null && ride.active === null}
            busy={busy}
            ttlMinutes={Math.round(config.booking_ttl_seconds / 60)}
            onBook={(code) => void booking.book(code)}
            onCancel={() => void booking.cancel()}
            onStart={() => void startRide()}
          />
        </CityMap>
        {ride.active && (
          <RidePanel
            ride={ride.active}
            scooter={scooters.get(ride.active.scooter_code)}
            zones={zones}
            now={now}
            busy={busy}
            currency={config.currency}
            onPause={() => void ride.pause()}
            onResume={() => void ride.resume()}
            onFinish={() => void ride.finish()}
          />
        )}
      </main>
      {ride.finished && <ReceiptModal ride={ride.finished} onClose={ride.dismissReceipt} />}
      {account !== null && user && (
        <AccountPanel
          user={user}
          activeRide={ride.active}
          history={history.rides}
          historyLoading={history.loading}
          emails={mailbox.emails}
          currency={config.currency}
          now={now}
          initialTab={account}
          onOpenMail={mailbox.markSeen}
          onClose={() => setAccount(null)}
        />
      )}
      {currentUser.state.status !== 'ready' && (
        <UserGate loading={currentUser.state.status === 'loading'} onRegister={currentUser.register} />
      )}
      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </div>
  )
}

export default App
