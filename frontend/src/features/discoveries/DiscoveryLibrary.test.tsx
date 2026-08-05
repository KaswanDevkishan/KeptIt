import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DiscoveryLibrary } from './DiscoveryLibrary'

const discovery = {
  id: 'c185d416-1d2b-4d4a-a846-d8b142e30372',
  original_url: 'https://github.com/keptit/example',
  canonical_url: 'https://github.com/keptit/example',
  platform: 'github',
  custom_title: 'Useful repository',
  personal_note: 'Try the testing pattern.',
  save_reason: 'For a later project',
  is_favourite: false,
  archived_at: null,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
  display_title: 'Useful repository',
  metadata: null,
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function page(results: unknown[] = []) {
  return json({ results, total: results.length, limit: 20, offset: 0 })
}

afterEach(() => vi.restoreAllMocks())

describe('Discovery library', () => {
  it('shows fetched metadata, title fallback, thumbnail safety, and pending state', async () => {
    const enriched = {
      ...discovery,
      custom_title: null,
      metadata: {
        status: 'succeeded',
        title: 'Fetched source title',
        description: 'A fetched description, distinct from the personal note.',
        site_name: 'GitHub',
        creator_or_publisher: 'keptit',
        thumbnail_url: 'https://images.example/preview.jpg',
        published_at: null,
        fetched_at: '2026-08-05T01:00:00Z',
        last_attempted_at: '2026-08-05T01:00:00Z',
        failure_code: null,
        failure_message_safe: null,
        provider: 'github_api',
        metadata_version: 1,
      },
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(page([enriched]))
    render(<DiscoveryLibrary />)
    expect(await screen.findByRole('heading', { name: 'Fetched source title' })).toBeInTheDocument()
    expect(screen.getByText(enriched.metadata.description)).toBeInTheDocument()
    expect(screen.getByText('GitHub · keptit')).toBeInTheDocument()
    expect(screen.getByRole('presentation')).toHaveAttribute('referrerpolicy', 'no-referrer')
    expect(screen.getByText(discovery.original_url)).toBeInTheDocument()
  })

  it('shows pending and failed states without fake thumbnails and retries', async () => {
    const pending = {
      ...discovery,
      id: 'pending',
      metadata: { status: 'pending', thumbnail_url: null },
    }
    const failed = {
      ...discovery,
      id: 'failed',
      custom_title: 'Failed card',
      metadata: { status: 'failed', thumbnail_url: null },
    }
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(page([pending, failed])))
    render(<DiscoveryLibrary />)
    expect(await screen.findByText('Source details pending.')).toBeInTheDocument()
    expect(screen.getByText('Source details unavailable.')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry metadata' }))
    expect(fetchMock.mock.calls.some((call) => call[0].toString().endsWith('/failed/enrich'))).toBe(
      true,
    )
  })

  it('shows a genuine empty state and the accessible save form', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(page())
    render(<DiscoveryLibrary />)
    expect(await screen.findByRole('heading', { name: 'Keep what matters.' })).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save your first Discovery' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toBeInTheDocument()
    expect(screen.getByLabelText(/Custom title/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Personal note/)).toBeInTheDocument()
  })

  it('validates URL locally, creates with credentials, and shows duplicate errors', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(page())
    render(<DiscoveryLibrary />)
    await screen.findByRole('heading', { name: 'Keep what matters.' })
    await userEvent.click(screen.getByRole('button', { name: 'Save your first Discovery' }))
    await userEvent.type(screen.getByLabelText('URL'), 'ftp://example.com/file')
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Save Discovery' }),
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid HTTP or HTTPS URL.')

    await userEvent.clear(screen.getByLabelText('URL'))
    await userEvent.type(screen.getByLabelText('URL'), discovery.original_url)
    fetchMock.mockResolvedValueOnce(json(discovery, 201)).mockResolvedValueOnce(page([discovery]))
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Save Discovery' }),
    )
    expect(await screen.findByRole('heading', { name: discovery.custom_title })).toBeInTheDocument()
    const createRequest = fetchMock.mock.calls.find(
      (call) =>
        call[0].toString().endsWith('/discoveries') && (call[1] as RequestInit).method === 'POST',
    )
    expect((createRequest?.[1] as RequestInit).credentials).toBe('include')

    await userEvent.click(screen.getByRole('button', { name: 'Save Discovery' }))
    await userEvent.type(screen.getByLabelText('URL'), discovery.original_url)
    fetchMock.mockResolvedValueOnce(
      json({ error: { code: 'duplicate_discovery', message: 'internal' } }, 409),
    )
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Save Discovery' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('already in your library')
  })

  it('renders, searches, filters, edits, favourites, and archives', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(page([discovery])))
    render(<DiscoveryLibrary />)
    expect(await screen.findByText(discovery.personal_note)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'repository')
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => call[0].toString().includes('q=repository'))).toBe(
        true,
      ),
    )
    await userEvent.selectOptions(screen.getByLabelText('Platform'), 'github')
    await userEvent.click(screen.getByLabelText('Favourites'))
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => call[0].toString().includes('favourite=true')),
      ).toBe(true),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.clear(screen.getByLabelText(/Custom title/))
    await userEvent.type(screen.getByLabelText(/Custom title/), 'Edited title')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(fetchMock.mock.calls.some((call) => (call[1] as RequestInit).method === 'PATCH')).toBe(
      true,
    )

    await userEvent.click(screen.getByRole('button', { name: /Favourite Useful repository/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Archive' }))
    expect(fetchMock.mock.calls.some((call) => call[0].toString().endsWith('/archive'))).toBe(true)
  })

  it('restores archived Discoveries and confirms permanent deletion', async () => {
    const archived = { ...discovery, archived_at: '2026-08-05T01:00:00Z' }
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(page([archived])))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<DiscoveryLibrary />)
    await screen.findByRole('heading', { name: discovery.custom_title })
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('cannot be undone'))
    expect(fetchMock.mock.calls.some((call) => call[0].toString().endsWith('/restore'))).toBe(true)
    expect(fetchMock.mock.calls.some((call) => (call[1] as RequestInit).method === 'DELETE')).toBe(
      true,
    )
  })
})
