import { FormEvent, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { AuthLayout } from './AuthLayout'
import { confirmPasswordReset } from './api'
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, validatePassword } from './validation'

function tokenFromFragment(fragment: string): string {
  return (
    new URLSearchParams(fragment.startsWith('#') ? fragment.slice(1) : fragment).get('token') ?? ''
  )
}

export function ResetPasswordPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [token] = useState(() => tokenFromFragment(location.hash))
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirmation?: string }>({})
  const [serverError, setServerError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    if (location.hash) navigate(location.pathname, { replace: true })
  }, [location.hash, location.pathname, navigate])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors = {
      password: validatePassword(password),
      confirmation: confirmation !== password ? 'Passwords do not match.' : undefined,
    }
    setErrors(nextErrors)
    setServerError('')
    if (Object.values(nextErrors).some(Boolean)) return
    if (!token) {
      setServerError('This password reset link is invalid or has expired.')
      return
    }
    setIsSubmitting(true)
    try {
      await confirmPasswordReset(token, password)
      setIsComplete(true)
    } catch (error) {
      setServerError(
        error instanceof ApiError && error.code === 'invalid_password_reset'
          ? 'This password reset link is invalid or has expired.'
          : 'Unable to reset your password. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Account recovery</p>
      <h1 className="auth-card__title">Choose a new password</h1>
      {isComplete ? (
        <div className="auth-success" role="status">
          <p>Your password has been reset. All existing sessions have been signed out.</p>
          <Link className="button button--primary" to="/login">
            Sign in
          </Link>
        </div>
      ) : (
        <>
          <p className="auth-card__intro">Use a new password for your KeptIt account.</p>
          {!token && (
            <div className="form-alert" role="alert">
              This password reset link is invalid or has expired.
            </div>
          )}
          <form className="auth-form" noValidate onSubmit={handleSubmit}>
            {serverError && (
              <div className="form-alert" role="alert">
                {serverError}
              </div>
            )}
            <label htmlFor="reset-password">New password</label>
            <input
              id="reset-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(errors.password)}
              aria-describedby="reset-password-help reset-password-error"
            />
            <p className="field-help" id="reset-password-help">
              Use {MIN_PASSWORD_LENGTH}–{MAX_PASSWORD_LENGTH.toLocaleString()} characters.
            </p>
            {errors.password && (
              <p className="field-error" id="reset-password-error">
                {errors.password}
              </p>
            )}
            <label htmlFor="reset-confirmation">Confirm password</label>
            <input
              id="reset-confirmation"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              aria-invalid={Boolean(errors.confirmation)}
              aria-describedby={errors.confirmation ? 'reset-confirmation-error' : undefined}
            />
            {errors.confirmation && (
              <p className="field-error" id="reset-confirmation-error">
                {errors.confirmation}
              </p>
            )}
            <button
              className="button button--primary auth-form__submit"
              disabled={isSubmitting || !token}
            >
              {isSubmitting ? 'Resetting password…' : 'Reset password'}
            </button>
          </form>
        </>
      )}
      {!isComplete && (
        <p className="auth-card__alternate">
          <Link to="/login">Back to sign in</Link>
        </p>
      )}
    </AuthLayout>
  )
}
