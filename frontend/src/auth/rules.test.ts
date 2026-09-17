import { describe, expect, it } from 'vitest'

import { PASSWORD_MIN_LENGTH, authErrorText, passwordHint, passwordProblem } from './rules'

describe('passwordProblem', () => {
  it('is about length only, counted in code points like the server', () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8)
    expect(passwordProblem('1234567')).toBe('too_short')
    expect(passwordProblem('12345678')).toBeNull()
    expect(passwordProblem('пароль!!')).toBeNull()
    expect(passwordProblem('😀'.repeat(8))).toBeNull() // 8 code points, 16 UTF-16 units
    expect(passwordProblem('x'.repeat(128))).toBeNull()
    expect(passwordProblem('x'.repeat(129))).toBe('too_long')
  })

  it('has a hint for every problem the server can report', () => {
    expect(passwordHint('too_short')).toBe('Пароль не короче 8 символов')
    expect(passwordHint('too_long')).toBe('Пароль не длиннее 128 символов')
    expect(passwordHint('something_new')).toBe('Проверьте пароль')
  })
})

describe('authErrorText', () => {
  it('translates the sign-in and registration codes and falls back to the server message', () => {
    expect(authErrorText('invalid_credentials', 'x')).toBe('Неверная почта или пароль')
    expect(authErrorText('password_not_set', 'x')).toBe(
      'У этого аккаунта ещё нет пароля — зарегистрируйтесь с этой почтой, история сохранится',
    )
    expect(authErrorText('email_taken', 'x')).toBe('Аккаунт с этой почтой уже есть — войдите')
    expect(authErrorText('wrong_password', 'x')).toBe('Текущий пароль неверный')
    expect(authErrorText('unknown_code', 'Server said so')).toBe('Server said so')
  })
})
