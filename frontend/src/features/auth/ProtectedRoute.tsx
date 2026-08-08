import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './AuthProvider'

export function ProtectedRoute() {
  const { isAuthenticated, isLoading, authError, refreshCurrentUser } = useAuth()
  const location = useLocation()

  if (isLoading)
    return (
      <div className="app-loading" role="status">
        Checking your session…
      </div>
    )
  if (authError)
    return (
      <div className="app-loading" role="alert">
        <p>{authError}</p>
        <button className="button button--primary" onClick={() => void refreshCurrentUser()}>
          Try again
        </button>
      </div>
    )
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
