import { useState, type FormEvent } from 'react'

import { emailHint, emailProblem } from '../account/email'
import { ApiError } from '../api/client'
import type { User } from '../api/types'

interface EmailFieldProps {
  user: User
  /** Saves the trimmed value ('' clears it); resolves with the updated user. */
  onSave: (email: string) => Promise<User>
}

/**
 * Where receipts go. The format is checked as the rider types (the same rules as the server,
 * see account/email.ts) and again by the server, whose answer names the failed rule too.
 */
export function EmailField({ user, onSave }: EmailFieldProps) {
  const [value, setValue] = useState(user.email ?? '')
  const [touched, setTouched] = useState(false)
  // a format rule the server refused (it names the rule, like the client does)
  const [serverProblem, setServerProblem] = useState<string | null>(null)
  // a failed request: not the rider's fault, so the field is not marked invalid
  const [saveFailed, setSaveFailed] = useState(false)
  // another account signs in with that address
  const [taken, setTaken] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<{ email: string | null } | null>(null)

  const trimmed = value.trim()
  const problem = trimmed ? emailProblem(trimmed) : 'empty'
  const formatHint = serverProblem ? emailHint(serverProblem) : touched && problem ? emailHint(problem) : null
  const dirty = trimmed !== (user.email ?? '')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    if (problem) {
      return
    }
    setSaving(true)
    setServerProblem(null)
    setSaveFailed(false)
    setTaken(false)
    try {
      const result = await onSave(trimmed)
      setSaved({ email: result.email })
      setValue(result.email ?? '')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'invalid_email') {
        setServerProblem(String(error.detail.problem ?? ''))
      } else if (error instanceof ApiError && error.code === 'email_taken') {
        setTaken(true)
      } else {
        setSaveFailed(true)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="email-field" onSubmit={submit} noValidate data-testid="email-field">
      <label className="email-field__label" htmlFor="account-email">
        Почта (вход и чеки)
      </label>
      <div className="email-field__row">
        <input
          id="account-email"
          className={`email-field__input ${formatHint ? 'email-field__input--invalid' : ''}`}
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="name@example.com"
          value={value}
          disabled={saving}
          aria-invalid={formatHint !== null}
          aria-describedby="account-email-hint"
          onChange={(event) => {
            setValue(event.target.value)
            setServerProblem(null)
            setSaveFailed(false)
            setTaken(false)
            setSaved(null)
          }}
          onBlur={() => setTouched(true)}
        />
        <button
          type="submit"
          className="btn btn--primary btn--small"
          disabled={saving || !dirty || (touched && problem !== null)}
        >
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </button>
      </div>
      <p
        id="account-email-hint"
        className={`email-field__hint ${formatHint || saveFailed || taken ? 'email-field__hint--error' : ''}`}
        aria-live="polite"
      >
        {formatHint ??
          (taken
            ? 'Аккаунт с этой почтой уже есть'
            : saveFailed
            ? 'Не удалось сохранить адрес, попробуйте ещё раз'
            : saved !== null
              ? `Сохранено: входите с ${saved.email ?? ''}, чеки придут туда же`
              : user.email
                ? `Чеки приходят на ${user.email}`
                : `Пока адрес не указан, чеки идут на ${user.mail_address || 'адрес из имени'}`)}
      </p>
    </form>
  )
}
