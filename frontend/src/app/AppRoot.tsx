import { Outlet } from 'react-router-dom'

import { AuthProvider } from '../features/auth/AuthProvider'

export function AppRoot() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}
