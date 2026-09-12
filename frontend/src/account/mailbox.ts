import type { Email, Money } from '../api/types'

/** Newest first; a message we already have (a replayed event) changes nothing. */
export function applyEmailEvent(inbox: Email[], incoming: Email): Email[] {
  if (inbox.some((e) => e.id === incoming.id)) {
    return inbox
  }
  return [incoming, ...inbox].sort((a, b) => b.id - a.id)
}

/** Messages with an id above the last one the user looked at (kept per tab, see storage). */
export function unreadCount(inbox: Email[], lastSeenId: number | null): number {
  return inbox.filter((e) => lastSeenId === null || e.id > lastSeenId).length
}

/**
 * The account page and the mailbox never compute money: they show the server's decimal string
 * exactly as it came, with the currency appended.
 */
export function displayMoney(amount: Money, currency: string): string {
  return `${amount} ${currency}`
}
