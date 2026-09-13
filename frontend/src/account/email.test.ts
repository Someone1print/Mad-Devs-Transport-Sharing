import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { EMAIL_HINTS, emailHint, emailProblem } from './email'

const here = dirname(fileURLToPath(import.meta.url))
const shared = JSON.parse(
  readFileSync(resolve(here, '../../../shared/email-cases.json'), 'utf8'),
) as { cases: { value: string; problem: string | null }[] }

describe('emailProblem', () => {
  it('reproduces every shared case exactly like the backend', () => {
    for (const { value, problem } of shared.cases) {
      expect(emailProblem(value), JSON.stringify(value)).toBe(problem)
    }
  })

  it('counts code points, not UTF-16 units, like Python', () => {
    const domain = '@example.com'
    const local = '😀' + 'a'.repeat(254 - domain.length - 1) // 254 code points, 255 UTF-16 units
    expect(emailProblem(local + domain)).toBeNull()
    expect(emailProblem(local + 'a' + domain)).toBe('too_long')
  })

  it('has a hint for every problem the backend can report', () => {
    const keys = new Set(shared.cases.map((c) => c.problem).filter((p): p is string => p !== null))
    for (const key of keys) {
      expect(EMAIL_HINTS[key as keyof typeof EMAIL_HINTS]).toBeTruthy()
    }
    expect(emailHint('something_new')).toBe('Проверьте формат адреса')
  })
})
