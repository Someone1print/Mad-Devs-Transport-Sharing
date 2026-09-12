import type { Email, Money } from '../api/types'

/** Newest first; a message we already have (a replayed event) changes nothing. */
export function applyEmailEvent(inbox: Email[], incoming: Email): Email[] {
  if (inbox.some((e) => e.id === incoming.id)) {
    return inbox
  }
  return [incoming, ...inbox].sort((a, b) => b.id - a.id)
}

/**
 * A fresh server list merged into what the tab already knows: an event that arrived while the
 * request was in flight survives, nothing is duplicated, newest first.
 */
export function mergeInbox(known: Email[], loaded: Email[]): Email[] {
  return loaded.reduce(applyEmailEvent, known)
}

/** Messages with an id above the last one the user looked at (kept per tab, see storage). */
export function unreadCount(inbox: Email[], lastSeenId: number | null): number {
  return inbox.filter((e) => lastSeenId === null || e.id > lastSeenId).length
}

/**
 * A stored "last seen" id is only trusted while the server still has that message: after the
 * database was recreated the ids restart, and a stale high-water mark would hide new receipts.
 */
export function validSeen(lastSeenId: number | null, inbox: Email[]): number | null {
  if (lastSeenId === null) {
    return null
  }
  const newest = inbox[0]?.id ?? 0
  return lastSeenId > newest ? null : lastSeenId
}

/**
 * The account page and the mailbox never compute money: they show the server's decimal string
 * exactly as it came, with the currency appended.
 */
export function displayMoney(amount: Money, currency: string): string {
  return `${amount} ${currency}`
}
