import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import * as authApi from './api'
import type { Credentials, PublicUser } from './api'

interface AuthContextValue {
  user: PublicUser | null
  isLoading: boolean
  isAuthenticated: boolean
  register: (credentials: Credentials) => Promise<PublicUser>
  login: (credentials: Credentials) => Promise<PublicUser>
  logout: () => Promise<void>
  refreshCurrentUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<PublicUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshCurrentUser = useCallback(async (signal?: AbortSignal) => {
    try {
      setUser(await authApi.getCurrentUser(signal))
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (error instanceof ApiError && error.status === 401) setUser(null)
      else setUser(null)
    } finally {
      if (!signal?.aborted) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refreshCurrentUser(controller.signal)
    return () => controller.abort()
  }, [refreshCurrentUser])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      register: async (credentials) => {
        const nextUser = await authApi.register(credentials)
        setUser(nextUser)
        return nextUser
      },
      login: async (credentials) => {
        const nextUser = await authApi.login(credentials)
        setUser(nextUser)
        return nextUser
      },
      logout: async () => {
        try {
          await authApi.logout()
        } finally {
          setUser(null)
        }
      },
      refreshCurrentUser: () => refreshCurrentUser(),
    }),
    [isLoading, refreshCurrentUser, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// The provider and its feature hook intentionally share this small module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
