import { useCallback, useEffect, useState } from 'react'

import { login as apiLogin, logout as apiLogout, registerAccount } from '../api/auth'
import { ApiError, SESSION_LOST_EVENT } from '../api/client'
import type { User } from '../api/types'
import { fetchMe } from '../api/users'

export type CurrentUserState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'ready'; user: User }

export interface CurrentUser {
  state: CurrentUserState
  register: (name: string, email: string, password: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** The server changed the user (e.g. the e-mail was saved): keep the state in step. */
  updateUser: (user: User) => void
  /** Re-read the user from the server (after a reconnect: another tab may have changed it). */
  refresh: () => Promise<void>
}

/**
 * Who is signed in, according to the server: the HttpOnly session cookie set at sign-in is
 * sent with every request, so on start we simply ask `GET /api/users/me`. Every tab of the
 * browser shares that cookie — two tabs are one user; a second user needs a private window.
 * A 401 anywhere (session expired or revoked from another device) drops back to the sign-in.
 */
export function useCurrentUser(): CurrentUser {
  const [state, setState] = useState<CurrentUserState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetchMe()
      .then((user) => {
        if (!cancelled) {
          setState({ status: 'ready', user })
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return
        }
        if (!(error instanceof ApiError && error.status === 401)) {
          console.warn('Could not check the session', error)
        }
        setState({ status: 'anonymous' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const onSessionLost = () => setState({ status: 'anonymous' })
    window.addEventListener(SESSION_LOST_EVENT, onSessionLost)
    return () => window.removeEventListener(SESSION_LOST_EVENT, onSessionLost)
  }, [])

  const register = useCallback(async (name: string, email: string, password: string) => {
    const result = await registerAccount(name, email, password)
    setState({ status: 'ready', user: result.user })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const result = await apiLogin(email, password)
    setState({ status: 'ready', user: result.user })
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch (error) {
      console.warn('Sign-out request failed; the session cookie may still be valid', error)
    }
    setState({ status: 'anonymous' })
  }, [])

  const updateUser = useCallback((user: User) => {
    setState({ status: 'ready', user })
  }, [])

  const refresh = useCallback(async () => {
    if (state.status !== 'ready') {
      return
    }
    try {
      updateUser(await fetchMe())
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) {
        console.warn('Could not refresh the user', error)
      }
    }
  }, [state, updateUser])

  return { state, register, login, logout, updateUser, refresh }
}
