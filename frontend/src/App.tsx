import { CityMap } from './components/CityMap'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">Transport Sharing</h1>
        <span className="app__subtitle">Аренда самокатов · Бишкек</span>
      </header>
      <main className="app__map">
        <CityMap />
      </main>
    </div>
  )
}

export default App
