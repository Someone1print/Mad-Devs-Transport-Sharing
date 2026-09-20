/**
 * Password rules and the texts of account errors. The server (backend/app/services/auth.py)
 * applies the same length rule and names the failed one in `problem`; lengths count code
 * points, like Python's len().
 */
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

export type PasswordProblem = 'too_short' | 'too_long'

export function passwordProblem(value: string): PasswordProblem | null {
  const length = [...value].length
  if (length < PASSWORD_MIN_LENGTH) {
    return 'too_short'
  }
  if (length > PASSWORD_MAX_LENGTH) {
    return 'too_long'
  }
  return null
}

const PASSWORD_HINTS: Record<PasswordProblem, string> = {
  too_short: `Пароль не короче ${PASSWORD_MIN_LENGTH} символов`,
  too_long: `Пароль не длиннее ${PASSWORD_MAX_LENGTH} символов`,
}

export function passwordHint(problem: string): string {
  return (PASSWORD_HINTS as Record<string, string>)[problem] ?? 'Проверьте пароль'
}

const AUTH_ERRORS: Record<string, string> = {
  invalid_credentials: 'Неверная почта или пароль',
  password_not_set:
    'У этого аккаунта ещё нет пароля — зарегистрируйтесь с этой почтой, история сохранится',
  email_taken: 'Аккаунт с этой почтой уже есть — войдите',
  wrong_password: 'Текущий пароль неверный',
  user_required: 'Войдите, чтобы продолжить',
}

/** The text for an account error code; unknown codes show the server's own message. */
export function authErrorText(code: string, serverMessage: string): string {
  return AUTH_ERRORS[code] ?? serverMessage
}
