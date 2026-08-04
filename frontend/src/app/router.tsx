import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'

import { AppPage } from '../features/auth/AppPage'
import { LoginPage } from '../features/auth/LoginPage'
import { ProtectedRoute } from '../features/auth/ProtectedRoute'
import { RegisterPage } from '../features/auth/RegisterPage'
import { LandingPage } from '../features/landing/LandingPage'
import { AppRoot } from './AppRoot'

export const routes: RouteObject[] = [
  {
    element: <AppRoot />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/login', element: <LoginPage /> },
      { element: <ProtectedRoute />, children: [{ path: '/app', element: <AppPage /> }] },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
