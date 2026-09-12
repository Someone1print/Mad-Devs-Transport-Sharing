import { useCallback, useEffect, useState } from 'react'

import { fetchEmails } from '../api/account'
import type { Email } from '../api/types'
import { applyEmailEvent, mergeInbox, unreadCount, validSeen } from './mailbox'
import type { LoadStatus } from './useRideHistory'

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
  status: LoadStatus
  refresh: () => Promise<void>
  /** Mark everything currently in the inbox as read (the user opened the mailbox tab). */
  markSeen: () => void
  handleEvent: (email: Email) => void
}

interface MailboxState {
  userId: number | null
  emails: Email[]
  seen: number | null
  status: LoadStatus
}

const EMPTY: MailboxState = { userId: null, emails: [], seen: null, status: 'loading' }

/** The rider's stored e-mails (the mailbox stub): loaded on start, pushed live, reloaded on demand. */
export function useMailbox(userId: number | null): Mailbox {
  const [state, setState] = useState<MailboxState>(EMPTY)
  const current = state.userId === userId ? state : EMPTY

  // a fresh list never discards an event that arrived while the request was in flight
  const applyLoaded = useCallback(
    (loaded: Email[]) => {
      setState((prev) => {
        const known = prev.userId === userId ? prev.emails : []
        const emails = mergeInbox(known, loaded)
        return { userId, emails, seen: validSeen(loadSeen(userId ?? -1), emails), status: 'ready' }
      })
    },
    [userId],
  )
  const applyFailure = useCallback(
    (error: unknown) => {
      console.warn('Could not load the mailbox', error)
      setState((prev) => ({
        userId,
        emails: prev.userId === userId ? prev.emails : [],
        seen: prev.userId === userId ? prev.seen : null,
        status: 'error',
      }))
    },
    [userId],
  )

  const refresh = useCallback(async () => {
    if (userId === null) {
      return
    }
    try {
      applyLoaded(await fetchEmails(userId))
    } catch (error) {
      applyFailure(error)
    }
  }, [userId, applyLoaded, applyFailure])

  useEffect(() => {
    if (userId === null) {
      return
    }
    let cancelled = false
    fetchEmails(userId)
      .then((loaded) => {
        if (!cancelled) {
          applyLoaded(loaded)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          applyFailure(error)
        }
      })
    return () => {
      cancelled = true
    }
  }, [userId, applyLoaded, applyFailure])

  const handleEvent = useCallback(
    (email: Email) => {
      setState((prev) => {
        const same = prev.userId === userId
        return {
          userId,
          emails: applyEmailEvent(same ? prev.emails : [], email),
          seen: same ? prev.seen : loadSeen(userId ?? -1),
          status: same ? prev.status : 'loading',
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

  return {
    emails: current.emails,
    unread: unreadCount(current.emails, current.seen),
    status: current.status,
    refresh,
    markSeen,
    handleEvent,
  }
}
