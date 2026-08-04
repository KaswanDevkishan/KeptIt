import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'

import { AppPage } from '../features/auth/AppPage'
import { LoginPage } from '../features/auth/LoginPage'
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage'
import { ProtectedRoute } from '../features/auth/ProtectedRoute'
import { RegisterPage } from '../features/auth/RegisterPage'
import { ResetPasswordPage } from '../features/auth/ResetPasswordPage'
import { LandingPage } from '../features/landing/LandingPage'
import { AppRoot } from './AppRoot'

export const routes: RouteObject[] = [
  {
    element: <AppRoot />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
      { element: <ProtectedRoute />, children: [{ path: '/app', element: <AppPage /> }] },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
