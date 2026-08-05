import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DiscoveryLibrary } from '../discoveries/DiscoveryLibrary'

const discovery = {
  id: 'c185d416-1d2b-4d4a-a846-d8b142e30372',
  original_url: 'https://example.com/recipe',
  canonical_url: 'https://example.com/recipe',
  platform: 'generic_web',
  custom_title: 'Tofu recipe',
  personal_note: null,
  save_reason: null,
  is_favourite: false,
  archived_at: null,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
  display_title: 'Tofu recipe',
  metadata: null,
}

const space = {
  id: 'c2a6e779-6a86-428d-a7fe-7e113c954cba',
  name: 'Recipes',
  description: null,
  discovery_count: 0,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.restoreAllMocks())

describe('Spaces UI', () => {
  it('creates, filters, assigns, removes, renames, and deletes a Space', async () => {
    let spaces: (typeof space)[] = []
    let assigned = false
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const path = input.toString()
      const method = (init as RequestInit | undefined)?.method ?? 'GET'
      if (path.includes('/spaces?'))
        return Promise.resolve(json({ items: spaces, next_cursor: null }))
      if (path.endsWith(`/spaces/${space.id}/discoveries?limit=100&archive=all`))
        return Promise.resolve(json({ items: assigned ? [discovery] : [], next_cursor: null }))
      if (path.includes(`/spaces/${space.id}/discoveries?limit=100&archive=`))
        return Promise.resolve(json({ items: assigned ? [discovery] : [], next_cursor: null }))
      if (path.endsWith('/spaces') && method === 'POST') {
        spaces = [{ ...space, name: 'Recipes' }]
        return Promise.resolve(json(spaces[0], 201))
      }
      if (path.endsWith(`/spaces/${space.id}`) && method === 'PATCH') {
        spaces = [{ ...spaces[0], name: 'Cooking' }]
        return Promise.resolve(json(spaces[0]))
      }
      if (path.endsWith(`/spaces/${space.id}`) && method === 'DELETE') {
        spaces = []
        assigned = false
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (path.includes(`/spaces/${space.id}/discoveries/${discovery.id}`)) {
        assigned = method === 'PUT'
        return Promise.resolve(
          method === 'DELETE'
            ? new Response(null, { status: 204 })
            : json({ id: 'membership', space_id: space.id, discovery_id: discovery.id }, 201),
        )
      }
      return Promise.resolve(json({ results: [discovery], total: 1, limit: 20, offset: 0 }))
    })

    render(<DiscoveryLibrary />)
    expect(await screen.findByRole('heading', { name: 'My Spaces' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All Discoveries' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Create Space' }))
    expect(screen.getByRole('dialog', { name: 'Create Space' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Space name'), '   ')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a Space name.')
    await userEvent.clear(screen.getByLabelText('Space name'))
    await userEvent.type(screen.getByLabelText('Space name'), 'Recipes')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(await screen.findByRole('button', { name: /Recipes/ })).toBeInTheDocument()

    await userEvent.click(screen.getByText('Add or remove Spaces'))
    await userEvent.click(within(screen.getByRole('article')).getByLabelText('Recipes'))
    await waitFor(() => expect(assigned).toBe(true))
    expect(screen.getByText('Spaces: Recipes')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Recipes/ }))
    expect(await screen.findByRole('heading', { name: 'Recipes', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tofu recipe' })).toBeInTheDocument()
    await userEvent.click(screen.getByText('Add or remove Spaces'))
    await userEvent.click(within(screen.getByRole('article')).getByLabelText('Recipes'))
    await waitFor(() => expect(assigned).toBe(false))
    expect(await screen.findByText('No discoveries in this space.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Rename Space' }))
    await userEvent.clear(screen.getByLabelText('Space name'))
    await userEvent.type(screen.getByLabelText('Space name'), 'Cooking')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByRole('heading', { name: 'Cooking', level: 1 })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Delete Space' }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveTextContent('does NOT delete Discoveries')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete Space' }))
    expect(await screen.findByRole('heading', { name: 'Your Discoveries' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Tofu recipe' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some((call) => (call[1] as RequestInit)?.method === 'PUT')).toBe(
      true,
    )
  })

  it('keeps a duplicate create dialog open with inline conflict feedback', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const path = input.toString()
      if (path.includes('/spaces?'))
        return Promise.resolve(json({ items: [space], next_cursor: null }))
      if (path.includes('/spaces/') && path.includes('/discoveries?'))
        return Promise.resolve(json({ items: [], next_cursor: null }))
      if (path.endsWith('/spaces') && (init as RequestInit)?.method === 'POST')
        return Promise.resolve(
          json({ error: { code: 'space_name_conflict', message: 'conflict' } }, 409),
        )
      return Promise.resolve(json({ results: [], total: 0, limit: 20, offset: 0 }))
    })
    render(<DiscoveryLibrary />)
    await screen.findByRole('button', { name: /Recipes/ })
    await userEvent.click(screen.getByRole('button', { name: 'Create Space' }))
    await userEvent.type(screen.getByLabelText('Space name'), 'recipes')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
    expect(screen.getByLabelText('Space name')).toHaveValue('recipes')
  })
})
