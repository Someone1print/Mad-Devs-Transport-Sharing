import { describe, expect, it } from 'vitest'

import type { Email } from '../api/types'
import { applyEmailEvent, displayMoney, mergeInbox, unreadCount, validSeen } from './mailbox'

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

describe('mergeInbox', () => {
  it('keeps an event that arrived while the list was loading, newest first, no duplicates', () => {
    const known = [email(4)] // pushed over the socket during the request
    const loaded = [email(3), email(2)] // the server answered before the receipt was written

    expect(mergeInbox(known, loaded).map((e) => e.id)).toEqual([4, 3, 2])
    expect(mergeInbox([], loaded)).toEqual(loaded)
    expect(mergeInbox(loaded, loaded).map((e) => e.id)).toEqual([3, 2])
  })
})

describe('validSeen', () => {
  it('drops a stored mark that points past everything the server has (ids restarted)', () => {
    expect(validSeen(7, [email(3), email(1)])).toBeNull()
    expect(validSeen(7, [])).toBeNull()
    expect(validSeen(3, [email(3), email(1)])).toBe(3)
    expect(validSeen(1, [email(3), email(1)])).toBe(1)
    expect(validSeen(null, [email(3)])).toBeNull()
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
