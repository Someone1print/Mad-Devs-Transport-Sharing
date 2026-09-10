import { CityMap } from './components/CityMap'
import { ScooterMarkers } from './components/ScooterMarkers'
import { STATUS_META, STATUS_ORDER } from './config/status'
import { useScooterFeed, type ConnectionState } from './realtime/useScooterFeed'
import './App.css'

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: 'Подключение…',
  live: 'Онлайн',
  reconnecting: 'Переподключение…',
}

function App() {
  const { scooters, connection } = useScooterFeed()
  const list = Array.from(scooters.values())
  const available = list.filter((scooter) => scooter.status === 'available').length

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
        <div className="app__stats">
          <span>
            {list.length} самокатов · {available} свободны
          </span>
          <span className={`connection connection--${connection}`}>
            {CONNECTION_LABEL[connection]}
          </span>
        </div>
      </header>
      <main className="app__map">
        <CityMap>
          <ScooterMarkers scooters={list} />
        </CityMap>
      </main>
    </div>
  )
}

export default App
