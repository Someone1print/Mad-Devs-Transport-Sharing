import { useState, type FormEvent } from 'react'

import { ApiError } from '../api/client'
import type { StoredUser } from '../user/storage'

interface UserGateProps {
  loading: boolean
  /** Riders this browser registered before, most recent first (empty on a first visit). */
  known: StoredUser[]
  onRegister: (name: string) => Promise<void>
  onContinue: (rider: StoredUser) => Promise<void>
}

/** First-visit screen: a name is all we need (no passwords in this demo). */
export function UserGate({ loading, known, onRegister, onContinue }: UserGateProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Введите имя')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onRegister(trimmed)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? `Не удалось создать пользователя: ${caught.message}`
          : 'Нет связи с сервером, попробуйте ещё раз',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const resume = async (rider: StoredUser) => {
    setSubmitting(true)
    setError(null)
    try {
      await onContinue(rider)
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 401
          ? `Пользователя «${rider.name}» больше нет: база была пересоздана`
          : 'Нет связи с сервером, попробуйте ещё раз',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="gate" role="dialog" aria-modal="true" aria-labelledby="gate-title">
      <form className="gate__card" onSubmit={submit}>
        <h2 id="gate-title" className="gate__title">
          Как вас зовут?
        </h2>
        <p className="gate__hint">
          Имя нужно, чтобы бронировать самокаты. Без пароля: сессия живёт в этой вкладке.
        </p>
        {known.length > 0 && (
          <div className="gate__known" data-testid="known-riders">
            {known.map((rider) => (
              <button
                key={rider.id}
                type="button"
                className="btn btn--ghost"
                disabled={loading || submitting}
                onClick={() => void resume(rider)}
              >
                Продолжить как {rider.name}
              </button>
            ))}
            <span className="gate__or">или новое имя:</span>
          </div>
        )}
        <input
          className="gate__input"
          autoFocus
          maxLength={64}
          placeholder="Например, Айбек"
          value={name}
          disabled={loading || submitting}
          onChange={(event) => setName(event.target.value)}
        />
        {error && <div className="gate__error">{error}</div>}
        <button className="btn btn--primary" type="submit" disabled={loading || submitting}>
          {loading ? 'Проверяем сессию…' : submitting ? 'Создаём…' : 'Продолжить'}
        </button>
      </form>
    </div>
  )
}
