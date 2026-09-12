import { useCallback, useEffect, useState } from 'react'

import { fetchEmails } from '../api/account'
import type { Email } from '../api/types'
import { applyEmailEvent, unreadCount } from './mailbox'

const SEEN_KEY = 'transport-sharing.mail-seen'

function loadSeen(userId: number): number | null {
  try {
    const raw = sessionStorage.getItem(`${SEEN_KEY}.${userId}`)
    return raw === null ? null : Number(raw)
  } catch {
    return null
  }
}

function saveSeen(userId: number, id: number): void {
  try {
    sessionStorage.setItem(`${SEEN_KEY}.${userId}`, String(id))
  } catch {
    // storage unavailable: the badge just shows everything as unread after a reload
  }
}

export interface Mailbox {
  emails: Email[]
  unread: number
  refresh: () => Promise<void>
  /** Mark everything currently in the inbox as read (the user opened the mailbox tab). */
  markSeen: () => void
  handleEvent: (email: Email) => void
}

interface MailboxState {
  userId: number | null
  emails: Email[]
  seen: number | null
}

/** The rider's stored e-mails (the mailbox stub): loaded on start, pushed live, reloaded on demand. */
export function useMailbox(userId: number | null): Mailbox {
  const [state, setState] = useState<MailboxState>({ userId: null, emails: [], seen: null })
  const emails = state.userId === userId ? state.emails : []
  const seen = state.userId === userId ? state.seen : null

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      const loaded = await fetchEmails(userId)
      setState({ userId, emails: loaded, seen: loadSeen(userId) })
    } catch (error) {
      console.warn('Could not load the mailbox', error)
    }
  }, [userId])

  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchEmails(userId)
      .then((loaded) => {
        if (!cancelled) {
          setState({ userId, emails: loaded, seen: loadSeen(userId) })
        }
      })
      .catch((error: unknown) => console.warn('Could not load the mailbox', error))
    return () => {
      cancelled = true
    }
  }, [userId])

  const handleEvent = useCallback(
    (email: Email) => {
      setState((prev) => {
        const same = prev.userId === userId
        return {
          userId,
          emails: applyEmailEvent(same ? prev.emails : [], email),
          seen: same ? prev.seen : loadSeen(userId ?? -1),
        }
      })
    },
    [userId],
  )

  const markSeen = useCallback(() => {
    if (userId === null) {
      return
    }
    setState((prev) => {
      if (prev.userId !== userId || prev.emails.length === 0) {
        return prev
      }
      const newest = prev.emails[0].id
      if (prev.seen === newest) {
        return prev
      }
      saveSeen(userId, newest)
      return { ...prev, seen: newest }
    })
  }, [userId])

  return { emails, unread: unreadCount(emails, seen), refresh, markSeen, handleEvent }
}
