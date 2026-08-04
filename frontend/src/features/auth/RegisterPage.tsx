import { FormEvent, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { AuthLayout } from './AuthLayout'
import { useAuth } from './AuthProvider'
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  validateEmail,
  validatePassword,
} from './validation'

interface Errors {
  email?: string
  password?: string
  confirmation?: string
}

export function RegisterPage() {
  const { register, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [serverError, setServerError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isLoading && isAuthenticated) return <Navigate to="/app" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors: Errors = {
      email: validateEmail(email),
      password: validatePassword(password),
      confirmation: confirmation !== password ? 'Passwords do not match.' : undefined,
    }
    setErrors(nextErrors)
    setServerError('')
    if (Object.values(nextErrors).some(Boolean)) return
    setIsSubmitting(true)
    try {
      await register({ email: email.trim(), password })
      navigate('/app', { replace: true })
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : 'Unable to create your account.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Start your private library</p>
      <h1 className="auth-card__title">Create your account</h1>
      <p className="auth-card__intro">
        Keep the links that matter, with the context you’ll want later.
      </p>
      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        {serverError && (
          <div className="form-alert" role="alert">
            {serverError}
          </div>
        )}
        <label htmlFor="register-email">Email</label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? 'register-email-error' : undefined}
        />
        {errors.email && (
          <p className="field-error" id="register-email-error">
            {errors.email}
          </p>
        )}
        <label htmlFor="register-password">Password</label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={Boolean(errors.password)}
          aria-describedby="password-help register-password-error"
        />
        <p className="field-help" id="password-help">
          Use {MIN_PASSWORD_LENGTH}–{MAX_PASSWORD_LENGTH.toLocaleString()} characters. Spaces are
          preserved.
        </p>
        {errors.password && (
          <p className="field-error" id="register-password-error">
            {errors.password}
          </p>
        )}
        <label htmlFor="confirm-password">Confirm password</label>
        <input
          id="confirm-password"
          name="confirmation"
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          aria-invalid={Boolean(errors.confirmation)}
          aria-describedby={errors.confirmation ? 'confirmation-error' : undefined}
        />
        {errors.confirmation && (
          <p className="field-error" id="confirmation-error">
            {errors.confirmation}
          </p>
        )}
        <button
          className="button button--primary auth-form__submit"
          disabled={isSubmitting || isLoading}
          type="submit"
        >
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="auth-card__alternate">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </AuthLayout>
  )
}
