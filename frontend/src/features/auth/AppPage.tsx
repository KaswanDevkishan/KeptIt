import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from './AuthProvider'

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
        <button
          className="button button--compact button--quiet"
          disabled={isLoggingOut}
          onClick={() => void handleLogout()}
          type="button"
        >
          {isLoggingOut ? 'Signing out…' : 'Log out'}
        </button>
      </header>
      <main className="app-placeholder">
        <p className="eyebrow">Your KeptIt</p>
        <h1>Welcome back.</h1>
        <div className="app-account">
          <p className="app-account__label">Account</p>
          <p className="app-account__email">{user?.email}</p>
        </div>
        <p>
          Your private library is coming next. For now, your account is ready and safely signed in.
        </p>
      </main>
    </div>
  )
}
