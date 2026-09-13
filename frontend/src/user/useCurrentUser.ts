import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import type { User } from '../api/types'
import { createUser, fetchMe } from '../api/users'
import {
  clearStoredUser,
  forgetRider,
  loadKnownRiders,
  loadStoredUser,
  saveStoredUser,
  type StoredUser,
} from './storage'

export type CurrentUserState =
  | { status: 'loading' }
  | { status: 'anonymous'; known: StoredUser[] }
  | { status: 'ready'; user: User }

export interface CurrentUser {
  state: CurrentUserState
  register: (name: string) => Promise<void>
  /** Ride again as someone this browser already registered (validated with the server). */
  continueAs: (rider: StoredUser) => Promise<void>
  /** The server changed the user (e.g. the e-mail was saved): keep the state in step. */
  updateUser: (user: User) => void
  signOut: () => void
}

/**
 * Restores the rider — this tab's, else the browser's most recent one — after checking the id
 * with the server; otherwise asks for a name (or offers the riders this browser knows).
 */
export function useCurrentUser(): CurrentUser {
  const [state, setState] = useState<CurrentUserState>(() =>
    loadStoredUser() ? { status: 'loading' } : { status: 'anonymous', known: loadKnownRiders() },
  )

  useEffect(() => {
    const stored = loadStoredUser()
    if (!stored) {
      return
    }
    let cancelled = false
    fetchMe(stored.id)
      .then((user) => {
        if (!cancelled) {
          saveStoredUser({ id: user.id, name: user.name })
          setState({ status: 'ready', user })
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError && error.status === 401) {
          // the database was reset since this browser registered: start over
          forgetRider(stored.id)
          setState({ status: 'anonymous', known: loadKnownRiders() })
        } else {
          // backend unreachable right now: keep the stored identity, the map still works
          setState({
            status: 'ready',
            user: { ...stored, email: null, mail_address: '', created_at: '' },
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const register = useCallback(async (name: string) => {
    const user = await createUser(name)
    saveStoredUser({ id: user.id, name: user.name })
    setState({ status: 'ready', user })
  }, [])

  const continueAs = useCallback(async (rider: StoredUser) => {
    try {
      const user = await fetchMe(rider.id)
      saveStoredUser({ id: user.id, name: user.name })
      setState({ status: 'ready', user })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        forgetRider(rider.id)
        setState({ status: 'anonymous', known: loadKnownRiders() })
      }
      throw error
    }
  }, [])

  const updateUser = useCallback((user: User) => {
    setState({ status: 'ready', user })
  }, [])

  const signOut = useCallback(() => {
    clearStoredUser()
    setState({ status: 'anonymous', known: loadKnownRiders() })
  }, [])

  return { state, register, continueAs, updateUser, signOut }
}
