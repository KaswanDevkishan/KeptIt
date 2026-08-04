import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../../app/router'

const genericMessage =
  'If an account exists for that email, password reset instructions have been sent.'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function unauthenticated() {
  return jsonResponse(
    { error: { code: 'unauthenticated', message: 'Authentication required.' } },
    401,
  )
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

afterEach(() => vi.restoreAllMocks())

describe('password recovery', () => {
  it('login links to the forgot-password form', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}, 401))
    renderAt('/login')

    expect(await screen.findByRole('link', { name: 'Forgot password?' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('renders forgot-password, validates email, and shows generic success', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(jsonResponse({ message: genericMessage }))
    renderAt('/forgot-password')

    expect(screen.getByRole('heading', { name: 'Reset your password' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'invalid')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset instructions' }))
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await userEvent.clear(screen.getByLabelText('Email'))
    await userEvent.type(screen.getByLabelText('Email'), 'unknown@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset instructions' }))
    expect(await screen.findByRole('status')).toHaveTextContent(genericMessage)
    const request = fetchMock.mock.calls[1][1] as RequestInit
    expect(JSON.parse(request.body as string)).toEqual({ email: 'unknown@example.com' })
  })

  it('renders reset form with a fragment token and validates password mismatch', async () => {
    vi.spyOn(globalThis, 'fetch')
    const router = renderAt('/reset-password#token=secret-token')

    expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()
    await waitFor(() => expect(router.state.location.hash).toBe(''))
    await userEvent.type(screen.getByLabelText('New password'), 'long enough password')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'different password')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))
    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
  })

  it('submits the in-memory token, never uses storage, and shows login action', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(jsonResponse({ message: 'Your password has been reset.' }))
    const localStorageSpy = vi.spyOn(localStorage, 'setItem')
    const sessionStorageSpy = vi.spyOn(sessionStorage, 'setItem')
    renderAt('/reset-password#token=secret-token')

    await userEvent.type(screen.getByLabelText('New password'), 'long enough password')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'long enough password')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    expect(await screen.findByRole('status')).toHaveTextContent('All existing sessions')
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({
      token: 'secret-token',
      new_password: 'long enough password',
    })
    expect(localStorageSpy).not.toHaveBeenCalled()
    expect(sessionStorageSpy).not.toHaveBeenCalled()
  })

  it('shows the same invalid-or-expired error for rejected tokens', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'invalid_password_reset',
              message: 'internal state must not be displayed',
            },
          },
          400,
        ),
      )
    renderAt('/reset-password#token=expired-token')
    await userEvent.type(screen.getByLabelText('New password'), 'long enough password')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'long enough password')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This password reset link is invalid or has expired.',
    )
    expect(screen.queryByText(/internal state/)).not.toBeInTheDocument()
  })
})
