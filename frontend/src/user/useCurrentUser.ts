import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import type { User } from '../api/types'
import { createUser, fetchMe } from '../api/users'
import { clearStoredUser, loadStoredUser, saveStoredUser } from './storage'

export type CurrentUserState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'ready'; user: User }

export interface CurrentUser {
  state: CurrentUserState
  register: (name: string) => Promise<void>
  signOut: () => void
}

/** Restores the rider from sessionStorage (validating the id) or asks for a name. */
export function useCurrentUser(): CurrentUser {
  const [state, setState] = useState<CurrentUserState>(() =>
    loadStoredUser() ? { status: 'loading' } : { status: 'anonymous' },
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
          // the database was reset since this tab registered: start over
          clearStoredUser()
          setState({ status: 'anonymous' })
        } else {
          // backend unreachable right now: keep the stored identity, the map still works
          setState({ status: 'ready', user: { ...stored, created_at: '' } })
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

  const signOut = useCallback(() => {
    clearStoredUser()
    setState({ status: 'anonymous' })
  }, [])

  return { state, register, signOut }
}
