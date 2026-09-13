import { request } from '../api/client'
import type { User } from '../api/types'

/**
 * The same format rules as backend/app/services/mail.py (email_problem): whitespace, exactly one
 * `@`, a local part, a domain with a dot, at most 254 characters. shared/email-cases.json pins
 * both copies. Format only — the stub cannot send a confirmation code, so existence is never
 * checked. Lengths count code points, like Python's len().
 */
export type EmailProblem = 'whitespace' | 'too_long' | 'at_sign' | 'local_part' | 'domain'

export const EMAIL_MAX_LENGTH = 254

// Unicode whitespace as JS defines it (\s); Python's str.isspace() agrees on every one of these
const WHITESPACE = /[\t\n\v\f\r \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]/u

export function emailProblem(value: string): EmailProblem | null {
  if (WHITESPACE.test(value)) {
    return 'whitespace'
  }
  if ([...value].length > EMAIL_MAX_LENGTH) {
    return 'too_long'
  }
  const parts = value.split('@')
  if (parts.length !== 2) {
    return 'at_sign'
  }
  const [localPart, domain] = parts
  if (!localPart) {
    return 'local_part'
  }
  if (
    !domain.includes('.') ||
    domain.startsWith('.') ||
    domain.endsWith('.') ||
    domain.includes('..')
  ) {
    return 'domain'
  }
  return null
}

export const EMAIL_HINTS: Record<EmailProblem, string> = {
  whitespace: 'В адресе не должно быть пробелов',
  too_long: `Адрес длиннее ${EMAIL_MAX_LENGTH} символов`,
  at_sign: 'В адресе должен быть ровно один знак @',
  local_part: 'Перед @ должно быть имя ящика',
  domain: 'После @ нужен домен с точкой, например example.com',
}

export function emailHint(problem: string): string {
  return (EMAIL_HINTS as Record<string, string>)[problem] ?? 'Проверьте формат адреса'
}

/** Save (or clear with an empty string) the address receipts go to. */
export function updateEmail(userId: number, email: string): Promise<User> {
  return request<User>('/api/users/me', { method: 'PATCH', body: { email }, userId })
}
