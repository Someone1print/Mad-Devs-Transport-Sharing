import { useState, type FormEvent } from 'react'

import { emailHint, emailProblem } from '../account/email'
import { ApiError } from '../api/client'
import { authErrorText, passwordHint, passwordProblem } from '../auth/rules'

interface UserGateProps {
  loading: boolean
  onRegister: (name: string, email: string, password: string) => Promise<void>
  onLogin: (email: string, password: string) => Promise<void>
}

type Mode = 'login' | 'register'

/**
 * Sign-in or registration. Format problems are shown under the field before anything is
 * sent (the same rules as the server's); the server's own answers — wrong password, an address
 * that is taken or has no mail server, an old account without a password — replace them.
 */
export function UserGate({ loading, onRegister, onLogin }: UserGateProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState(false)
  const [serverEmailProblem, setServerEmailProblem] = useState<string | null>(null)
  const [serverPasswordProblem, setServerPasswordProblem] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const trimmedEmail = email.trim()
  const localEmailProblem = trimmedEmail ? emailProblem(trimmedEmail) : 'empty'
  const localPasswordProblem = password ? passwordProblem(password) : 'too_short'
  const nameMissing = mode === 'register' && !name.trim()
  const emailText = serverEmailProblem
    ? emailHint(serverEmailProblem)
    : touched && localEmailProblem
      ? emailHint(localEmailProblem)
      : null
  const passwordText = serverPasswordProblem
    ? passwordHint(serverPasswordProblem)
    : touched && mode === 'register' && localPasswordProblem
      ? passwordHint(localPasswordProblem)
      : null

  const switchMode = (next: Mode) => {
    setMode(next)
    setTouched(false)
    setError(null)
    setServerEmailProblem(null)
    setServerPasswordProblem(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    setError(null)
    setServerEmailProblem(null)
    setServerPasswordProblem(null)
    if (localEmailProblem || nameMissing || (mode === 'register' && localPasswordProblem)) {
      return
    }
    if (mode === 'login' && !password) {
      setError('Введите пароль')
      return
    }
    setSubmitting(true)
    try {
      if (mode === 'register') {
        await onRegister(name.trim(), trimmedEmail, password)
      } else {
        await onLogin(trimmedEmail, password)
      }
    } catch (caught) {
      if (caught instanceof ApiError) {
        const problem = typeof caught.detail.problem === 'string' ? caught.detail.problem : null
        if (caught.code === 'invalid_email' && problem) {
          setServerEmailProblem(problem)
        } else if (caught.code === 'invalid_password' && problem) {
          setServerPasswordProblem(problem)
        } else {
          setError(authErrorText(caught.code, caught.message))
        }
      } else {
        setError('Нет связи с сервером, попробуйте ещё раз')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const pending = loading || submitting

  return (
    <div className="gate" role="dialog" aria-modal="true" aria-labelledby="gate-title">
      <form className="gate__card" onSubmit={submit} noValidate>
        <h2 id="gate-title" className="gate__title">
          {mode === 'login' ? 'Вход' : 'Регистрация'}
        </h2>
        <div className="gate__switch" role="tablist" aria-label="Вход или регистрация">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`gate__mode ${mode === 'login' ? 'gate__mode--active' : ''}`}
            onClick={() => switchMode('login')}
            disabled={pending}
          >
            Войти
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`gate__mode ${mode === 'register' ? 'gate__mode--active' : ''}`}
            onClick={() => switchMode('register')}
            disabled={pending}
          >
            Зарегистрироваться
          </button>
        </div>
        {mode === 'register' && (
          <label className="gate__field">
            <span className="gate__label">Имя</span>
            <input
              className="gate__input"
              autoFocus
              maxLength={64}
              autoComplete="name"
              placeholder="Например, Айбек"
              value={name}
              disabled={pending}
              onChange={(event) => setName(event.target.value)}
            />
            {touched && nameMissing && <span className="gate__hint gate__hint--error">Введите имя</span>}
          </label>
        )}
        <label className="gate__field">
          <span className="gate__label">Почта</span>
          <input
            id="gate-email"
            className={`gate__input ${emailText ? 'gate__input--invalid' : ''}`}
            type="email"
            inputMode="email"
            autoComplete="email"
            autoFocus={mode === 'login'}
            placeholder="name@gmail.com"
            value={email}
            disabled={pending}
            aria-invalid={emailText !== null}
            onChange={(event) => {
              setEmail(event.target.value)
              setServerEmailProblem(null)
            }}
          />
          {emailText && <span className="gate__hint gate__hint--error">{emailText}</span>}
        </label>
        <label className="gate__field">
          <span className="gate__label">Пароль</span>
          <input
            id="gate-password"
            className={`gate__input ${passwordText ? 'gate__input--invalid' : ''}`}
            type="password"
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            value={password}
            disabled={pending}
            aria-invalid={passwordText !== null}
            onChange={(event) => {
              setPassword(event.target.value)
              setServerPasswordProblem(null)
            }}
          />
          <span className={`gate__hint ${passwordText ? 'gate__hint--error' : ''}`}>
            {passwordText ?? (mode === 'register' ? 'Не короче 8 символов, остальное на ваш вкус' : '')}
          </span>
        </label>
        {error && (
          <div className="gate__error" role="alert">
            {error}
          </div>
        )}
        <button className="btn btn--primary" type="submit" disabled={pending}>
          {loading
            ? 'Проверяем сессию…'
            : submitting
              ? mode === 'login'
                ? 'Входим…'
                : 'Создаём аккаунт…'
              : mode === 'login'
                ? 'Войти'
                : 'Зарегистрироваться'}
        </button>
        <p className="gate__note">
          Две вкладки этого браузера — один пользователь. Второго пользователя откройте в окне
          инкогнито или в другом браузере.
        </p>
      </form>
    </div>
  )
}
