import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DiscoveryLibrary } from '../discoveries/DiscoveryLibrary'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.restoreAllMocks())

describe('Tags UI', () => {
  it('renders the distinct empty state and validates Tag creation', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const path = input.toString()
      if (path.includes('/tags?') || path.includes('/spaces?'))
        return Promise.resolve(json({ items: [], next_cursor: null }))
      return Promise.resolve(json({ results: [], total: 0, limit: 20, offset: 0 }))
    })
    render(<DiscoveryLibrary />)
    expect(
      await screen.findByText('No Tags yet. Tags describe subjects across Spaces.'),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Create Tag' }))
    const dialog = screen.getByRole('dialog', { name: 'Create Tag' })
    await userEvent.type(within(dialog).getByLabelText('Tag name'), '   ')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create Tag' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('1 to 50 characters')
  })

  it('renders neutral chips and activates a single Tag filter', async () => {
    const tag = {
      id: 'tag-id',
      name: 'A very long but accessible Tag name',
      discovery_count: 1,
      created_at: '2026-08-05T00:00:00Z',
      updated_at: '2026-08-05T00:00:00Z',
    }
    const discovery = {
      id: 'discovery-id',
      original_url: 'https://example.com',
      canonical_url: 'https://example.com',
      platform: 'generic_web',
      custom_title: 'Tagged item',
      personal_note: null,
      save_reason: null,
      is_favourite: false,
      archived_at: null,
      created_at: '2026-08-05T00:00:00Z',
      updated_at: '2026-08-05T00:00:00Z',
      display_title: 'Tagged item',
      metadata: null,
      tags: [{ id: tag.id, name: tag.name }],
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const path = input.toString()
      if (path.includes('/tags?')) return Promise.resolve(json({ items: [tag], next_cursor: null }))
      if (path.includes('/spaces?')) return Promise.resolve(json({ items: [], next_cursor: null }))
      return Promise.resolve(json({ results: [discovery], total: 1, limit: 20, offset: 0 }))
    })
    render(<DiscoveryLibrary />)
    const chip = await screen.findByRole('button', { name: tag.name })
    await userEvent.click(chip)
    expect(
      await screen.findByRole('heading', { name: `Your Discoveries · ${tag.name}` }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[0].toString().includes('tag_id=tag-id')),
      ).toBe(true),
    )
    expect(screen.getByRole('button', { name: 'Clear Tag filter' })).toBeInTheDocument()
  })
})
