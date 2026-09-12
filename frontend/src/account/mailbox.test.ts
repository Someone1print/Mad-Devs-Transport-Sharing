import { describe, expect, it } from 'vitest'

import type { Email } from '../api/types'
import { applyEmailEvent, displayMoney, unreadCount } from './mailbox'

function email(id: number): Email {
  return {
    id,
    to_address: 'dana@example.invalid',
    subject: `Чек ${id}`,
    body: 'Итого: 5.00 KGS',
    dedup_key: `ride:${id}:receipt`,
    created_at: '2026-09-12T12:00:00Z',
  }
}

describe('applyEmailEvent', () => {
  it('prepends a new message and ignores one it already has', () => {
    const inbox = [email(2), email(1)]

    expect(applyEmailEvent(inbox, email(3)).map((e) => e.id)).toEqual([3, 2, 1])
    expect(applyEmailEvent(inbox, email(2))).toBe(inbox)
  })
})

describe('unreadCount', () => {
  it('counts messages newer than the last seen id', () => {
    const inbox = [email(5), email(3), email(1)]

    expect(unreadCount(inbox, 3)).toBe(1)
    expect(unreadCount(inbox, null)).toBe(3)
    expect(unreadCount(inbox, 5)).toBe(0)
  })
})

describe('displayMoney', () => {
  it('shows the server string as is (no arithmetic on the client)', () => {
    expect(displayMoney('7.50', 'KGS')).toBe('7.50 KGS')
    expect(displayMoney('0.03', 'KGS')).toBe('0.03 KGS')
  })
})
