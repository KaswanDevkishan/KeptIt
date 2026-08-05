import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from './AuthProvider'
import { DiscoveryLibrary } from '../discoveries/DiscoveryLibrary'

export function AppPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  async function handleLogout() {
    setIsLoggingOut(true)
    const logoutRequest = logout()
    navigate('/', { replace: true })
    try {
      await logoutRequest
    } catch {
      // The local session is cleared by the provider even when logout is already invalid.
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="wordmark" to="/app" aria-label="KeptIt app home">
          KeptIt<span aria-hidden="true">.</span>
        </Link>
        <div className="app-user">
          <span>{user?.email}</span>
          <button
            className="button button--compact button--quiet"
            disabled={isLoggingOut}
            onClick={() => void handleLogout()}
            type="button"
          >
            {isLoggingOut ? 'Signing out…' : 'Log out'}
          </button>
        </div>
      </header>
      <main>
        <DiscoveryLibrary />
      </main>
    </div>
  )
}
