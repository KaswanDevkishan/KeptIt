import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routes } from '../../app/router'

const publicUser = {
  id: '1c76ee34-95c9-4daf-82d8-012a3fad33c4',
  email: 'person@example.com',
  is_active: true,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function unauthenticated() {
  return jsonResponse(
    { error: { code: 'not_authenticated', message: 'Authentication required.' } },
    401,
  )
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

afterEach(() => vi.restoreAllMocks())

describe('frontend authentication', () => {
  it('renders registration and validates email, password length, and mismatch', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(unauthenticated())
    renderAt('/register')
    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'invalid')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'short')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'different')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Password must be at least 12 characters.')).toBeInTheDocument()
    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
  })

  it('registers with trimmed email, preserves password, and navigates without persisting tokens', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(jsonResponse(publicUser, 201))
    const localStorageSpy = vi.spyOn(Storage.prototype, 'setItem')
    const router = renderAt('/register')
    await userEvent.type(await screen.findByLabelText('Email'), '  person@example.com ')
    await userEvent.type(
      screen.getByLabelText('Password', { exact: true }),
      ' password keeps spaces ',
    )
    await userEvent.type(screen.getByLabelText('Confirm password'), ' password keeps spaces ')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
    const request = fetchMock.mock.calls[1][1] as RequestInit
    expect(request.credentials).toBe('include')
    expect(JSON.parse(request.body as string)).toEqual({
      email: 'person@example.com',
      password: ' password keeps spaces ',
    })
    expect(localStorageSpy).not.toHaveBeenCalled()
  })

  it('shows the duplicate-registration error safely', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: 'email_registered', message: 'internal text' } }, 409),
      )
    renderAt('/register')
    await userEvent.type(await screen.findByLabelText('Email'), 'person@example.com')
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), 'valid password')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'valid password')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An account with this email already exists.',
    )
  })

  it('renders login, displays a generic invalid-login error, and navigates on success', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(unauthenticated())
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: 'invalid_credentials', message: 'Internal authentication detail.' } },
          401,
        ),
      )
    const router = renderAt('/login')
    expect(await screen.findByRole('heading', { name: 'Sign in to KeptIt' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Email'), 'person@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')

    fetchMock.mockResolvedValueOnce(jsonResponse(publicUser))
    await userEvent.clear(screen.getByLabelText('Password'))
    await userEvent.type(screen.getByLabelText('Password'), 'correct password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
  })

  it('checks the current user before allowing or redirecting protected content', async () => {
    let resolveCheck!: (response: Response) => void
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCheck = resolve
        }),
    )
    const router = renderAt('/app')
    expect(screen.getByRole('status')).toHaveTextContent('Checking your session')
    expect(screen.queryByText(/private library is coming next/i)).not.toBeInTheDocument()
    resolveCheck(unauthenticated())
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })

  it('keeps protected content unresolved when the current-user check fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))
    const router = renderAt('/app')

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to verify your session')
    expect(router.state.location.pathname).toBe('/app')
    expect(screen.queryByRole('heading', { name: 'Your Discoveries' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('redirects when a protected data request returns 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) =>
      Promise.resolve(
        input.toString().includes('/users/me') ? jsonResponse(publicUser) : unauthenticated(),
      ),
    )
    const router = renderAt('/app')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(screen.queryByText('Keep what matters.')).not.toBeInTheDocument()
  })

  it('shows an authenticated account separately from the protected-page heading', async () => {
    const userWithLongEmail = {
      ...publicUser,
      email: 'person-with-a-deliberately-long-address@subdomain.example.com',
    }
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(userWithLongEmail))
      .mockResolvedValueOnce(jsonResponse({ results: [], total: 0, limit: 20, offset: 0 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    const router = renderAt('/app')
    expect(await screen.findByRole('heading', { name: 'Your Discoveries' })).toBeInTheDocument()
    expect(screen.getByText(userWithLongEmail.email)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: new RegExp(userWithLongEmail.email) })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('links landing-page actions to authentication routes', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(unauthenticated())
    renderAt('/')
    expect(await screen.findByRole('link', { name: 'Get started' })).toHaveAttribute(
      'href',
      '/register',
    )
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0]).toHaveAttribute('href', '/login')
  })
})
