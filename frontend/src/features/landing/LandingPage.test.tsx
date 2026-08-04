import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { LandingPage } from './LandingPage'

describe('LandingPage', () => {
  it('presents the product promise and primary actions', () => {
    const router = createMemoryRouter([{ path: '/', element: <LandingPage /> }])
    render(<RouterProvider router={router} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Never lose anything interesting on the internet again.',
    )
    expect(screen.getByRole('button', { name: 'Get started' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Sign in' })).toHaveLength(2)
  })
})
