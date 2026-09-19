import { useState, type FormEvent } from 'react'

import { ApiError } from '../api/client'
import { authErrorText, passwordHint, passwordProblem } from '../auth/rules'

interface PasswordFieldProps {
  /** Changes the password; other devices are signed out by the server. */
  onChange: (currentPassword: string, newPassword: string) => Promise<void>
}

/** Change the password from the account: the current one, then a new one of 8+ characters. */
export function PasswordField({ onChange }: PasswordFieldProps) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [touched, setTouched] = useState(false)
  const [serverProblem, setServerProblem] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const problem = next ? passwordProblem(next) : 'too_short'
  const hint = serverProblem ? passwordHint(serverProblem) : touched && problem ? passwordHint(problem) : null

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    setError(null)
    setServerProblem(null)
    setDone(false)
    if (problem || !current) {
      if (!current) {
        setError('Введите текущий пароль')
      }
      return
    }
    setSaving(true)
    try {
      await onChange(current, next)
      setCurrent('')
      setNext('')
      setTouched(false)
      setDone(true)
    } catch (caught) {
      if (caught instanceof ApiError) {
        const detail = typeof caught.detail.problem === 'string' ? caught.detail.problem : null
        if (caught.code === 'invalid_password' && detail) {
          setServerProblem(detail)
        } else {
          setError(authErrorText(caught.code, caught.message))
        }
      } else {
        setError('Не удалось сменить пароль, попробуйте ещё раз')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="password-field" onSubmit={submit} noValidate data-testid="password-field">
      <label className="email-field__label" htmlFor="account-current-password">
        Текущий пароль
      </label>
      <input
        id="account-current-password"
        className="email-field__input"
        type="password"
        autoComplete="current-password"
        value={current}
        disabled={saving}
        onChange={(event) => {
          setCurrent(event.target.value)
          setError(null)
          setDone(false)
        }}
      />
      <label className="email-field__label" htmlFor="account-new-password">
        Новый пароль
      </label>
      <div className="email-field__row">
        <input
          id="account-new-password"
          className={`email-field__input ${hint ? 'email-field__input--invalid' : ''}`}
          type="password"
          autoComplete="new-password"
          value={next}
          disabled={saving}
          aria-invalid={hint !== null}
          aria-describedby="account-new-password-hint"
          onChange={(event) => {
            setNext(event.target.value)
            setServerProblem(null)
            setDone(false)
          }}
        />
        <button type="submit" className="btn btn--primary btn--small" disabled={saving}>
          {saving ? 'Меняем…' : 'Сменить'}
        </button>
      </div>
      <p
        id="account-new-password-hint"
        className={`email-field__hint ${hint || error ? 'email-field__hint--error' : ''}`}
        aria-live="polite"
      >
        {hint ??
          error ??
          (done
            ? 'Пароль изменён; на других устройствах нужно войти заново'
            : 'Не короче 8 символов; после смены другие устройства выйдут из аккаунта')}
      </p>
    </form>
  )
}
