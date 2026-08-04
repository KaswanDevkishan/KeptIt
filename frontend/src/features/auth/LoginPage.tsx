import { FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './AuthProvider'
import { validateEmail, validatePassword } from './validation'

function safeDestination(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/app'
}

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [serverError, setServerError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const destination = safeDestination((location.state as { from?: unknown } | null)?.from)

  if (!isLoading && isAuthenticated) return <Navigate to="/app" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors = { email: validateEmail(email), password: validatePassword(password, false) }
    setErrors(nextErrors)
    setServerError('')
    if (Object.values(nextErrors).some(Boolean)) return
    setIsSubmitting(true)
    try {
      await login({ email: email.trim(), password })
      navigate(destination, { replace: true })
    } catch (error) {
      setServerError(
        error instanceof ApiError && error.status === 401
          ? 'Email or password is incorrect.'
          : error instanceof ApiError
            ? error.message
            : 'Unable to sign in.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Welcome back</p>
      <h1 className="auth-card__title">Sign in to KeptIt</h1>
      <p className="auth-card__intro">Your private corner of the internet is waiting.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        {serverError && (
          <div className="form-alert" role="alert">
            {serverError}
          </div>
        )}
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? 'login-email-error' : undefined}
        />
        {errors.email && (
          <p className="field-error" id="login-email-error">
            {errors.email}
          </p>
        )}
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? 'login-password-error' : undefined}
        />
        {errors.password && (
          <p className="field-error" id="login-password-error">
            {errors.password}
          </p>
        )}
        <Link className="auth-form__recovery" to="/forgot-password">
          Forgot password?
        </Link>
        <button
          className="button button--primary auth-form__submit"
          disabled={isSubmitting || isLoading}
          type="submit"
        >
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="auth-card__alternate">
        New to KeptIt? <Link to="/register">Create an account</Link>
      </p>
    </AuthLayout>
  )
}
