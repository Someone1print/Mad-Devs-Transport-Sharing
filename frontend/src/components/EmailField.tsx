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
  const [serverHint, setServerHint] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAs, setSavedAs] = useState<string | null>(null)

  const trimmed = value.trim()
  const problem = trimmed ? emailProblem(trimmed) : null
  const hint = serverHint ?? (touched && problem ? emailHint(problem) : null)
  const dirty = trimmed !== (user.email ?? '')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    if (problem) {
      return
    }
    setSaving(true)
    setServerHint(null)
    try {
      const saved = await onSave(trimmed)
      setSavedAs(saved.email)
      setValue(saved.email ?? '')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'invalid_email') {
        setServerHint(emailHint(String(error.detail.problem ?? '')))
      } else {
        setServerHint('Не удалось сохранить адрес, попробуйте ещё раз')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="email-field" onSubmit={submit} noValidate data-testid="email-field">
      <label className="email-field__label" htmlFor="account-email">
        Почта для чеков
      </label>
      <div className="email-field__row">
        <input
          id="account-email"
          className={`email-field__input ${hint ? 'email-field__input--invalid' : ''}`}
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder={user.mail_address}
          value={value}
          disabled={saving}
          aria-invalid={hint !== null}
          aria-describedby="account-email-hint"
          onChange={(event) => {
            setValue(event.target.value)
            setServerHint(null)
            setSavedAs(null)
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
      <p id="account-email-hint" className={`email-field__hint ${hint ? 'email-field__hint--error' : ''}`}>
        {hint ??
          (savedAs !== null
            ? savedAs
              ? `Сохранено: чеки будут приходить на ${savedAs}`
              : `Адрес очищен: чеки идут на ${user.mail_address}`
            : user.email
              ? `Чеки приходят на ${user.email}`
              : `Пока адрес не указан, чеки идут на ${user.mail_address}`)}
      </p>
    </form>
  )
}
