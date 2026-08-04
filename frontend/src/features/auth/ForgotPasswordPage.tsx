import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { AuthLayout } from './AuthLayout'
import { requestPasswordReset } from './api'
import { validateEmail } from './validation'

const GENERIC_SUCCESS =
  'If an account exists for that email, password reset instructions have been sent.'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState('')
  const [serverError, setServerError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextError = validateEmail(email) ?? ''
    setEmailError(nextError)
    setServerError('')
    if (nextError) return
    setIsSubmitting(true)
    try {
      await requestPasswordReset(email.trim())
      setIsComplete(true)
    } catch {
      setServerError('Unable to request a password reset. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Account recovery</p>
      <h1 className="auth-card__title">Reset your password</h1>
      {isComplete ? (
        <div className="auth-success" role="status">
          <p>{GENERIC_SUCCESS}</p>
          <p>Check the development outbox or your email, then follow the reset link.</p>
        </div>
      ) : (
        <>
          <p className="auth-card__intro">
            Enter your account email and we’ll send password reset instructions if it matches an
            account.
          </p>
          <form className="auth-form" noValidate onSubmit={handleSubmit}>
            {serverError && (
              <div className="form-alert" role="alert">
                {serverError}
              </div>
            )}
            <label htmlFor="forgot-email">Email</label>
            <input
              id="forgot-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(emailError)}
              aria-describedby={emailError ? 'forgot-email-error' : undefined}
            />
            {emailError && (
              <p className="field-error" id="forgot-email-error">
                {emailError}
              </p>
            )}
            <button className="button button--primary auth-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Sending instructions…' : 'Send reset instructions'}
            </button>
          </form>
        </>
      )}
      <p className="auth-card__alternate">
        <Link to="/login">Back to sign in</Link>
      </p>
    </AuthLayout>
  )
}
