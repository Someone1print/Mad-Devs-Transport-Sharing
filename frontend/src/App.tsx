import { usePublicConfig } from './api/config'
import { formatRemaining, remainingSeconds, warningWindowSeconds } from './booking/bookingState'
import { useBooking } from './booking/useBooking'
import { CityMap } from './components/CityMap'
import { MyBooking } from './components/MyBooking'
import { ScooterMarkers } from './components/ScooterMarkers'
import { ToastStack } from './components/Toasts'
import { UserGate } from './components/UserGate'
import { STATUS_META, STATUS_ORDER } from './config/status'
import { useNow } from './hooks/useNow'
import { useToasts } from './hooks/useToasts'
import { useScooterFeed, type ConnectionState } from './realtime/useScooterFeed'
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
  const currentUser = useCurrentUser()
  const user = currentUser.state.status === 'ready' ? currentUser.state.user : null
  const userId = user?.id ?? null
  const { toasts, notify, dismiss } = useToasts()
  const booking = useBooking({ userId, notify })
  const { scooters, connection } = useScooterFeed({
    userId,
    onBookingEvent: booking.handleEvent,
  })

  const list = Array.from(scooters.values())
  const available = list.filter((scooter) => scooter.status === 'available').length
  const left = booking.active ? remainingSeconds(booking.active, now) : null
  const expiringSoon =
    booking.active !== null &&
    left !== null &&
    left <= warningWindowSeconds(booking.active, config.booking_warn_before_seconds)

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
        </ul>
        {booking.active && (
          <MyBooking booking={booking.active} now={now} busy={booking.busy} onCancel={booking.cancel} />
        )}
        <div className="app__stats">
          <span>
            {list.length} самокатов · {available} свободны
          </span>
          {user && (
            <span className="app__user">
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
      {expiringSoon && booking.active && left !== null && (
        <div className="banner" role="alert">
          Бронь {booking.active.scooter_code} истекает через {formatRemaining(left)}. Начните
          поездку или продлите бронь, иначе самокат снова станет свободным.
        </div>
      )}
      <main className="app__map">
        <CityMap>
          <ScooterMarkers
            scooters={list}
            myBooking={booking.active}
            now={now}
            canBook={user !== null}
            busy={booking.busy}
            ttlMinutes={Math.round(config.booking_ttl_seconds / 60)}
            onBook={(code) => void booking.book(code)}
            onCancel={() => void booking.cancel()}
          />
        </CityMap>
      </main>
      {currentUser.state.status !== 'ready' && (
        <UserGate loading={currentUser.state.status === 'loading'} onRegister={currentUser.register} />
      )}
      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </div>
  )
}

export default App
