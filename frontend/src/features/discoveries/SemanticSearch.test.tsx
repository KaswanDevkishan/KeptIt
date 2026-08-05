import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DiscoveryLibrary } from './DiscoveryLibrary'

const discovery = {
  id: 'c185d416-1d2b-4d4a-a846-d8b142e30372',
  original_url: 'https://example.com/ghost-town',
  canonical_url: 'https://example.com/ghost-town',
  platform: 'youtube',
  custom_title: 'Fukushima ghost town documentary',
  personal_note: null,
  save_reason: null,
  is_favourite: true,
  archived_at: null,
  created_at: '2026-08-05T00:00:00Z',
  updated_at: '2026-08-05T00:00:00Z',
  display_title: 'Fukushima ghost town documentary',
  metadata: null,
  tags: [{ id: 'tag-1', name: 'Japan' }],
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function status(name = 'succeeded') {
  return {
    status: name,
    is_searchable: name === 'succeeded',
    generated_at: null,
    last_attempted_at: null,
    can_index: name === 'unavailable' || name === 'stale',
    can_retry: name === 'failed' || name === 'stale',
    retry_after_seconds: null,
    error: null,
  }
}

function semantic(
  items: unknown[] = [{ discovery, relevance: { match_reasons: ['summary'] } }],
  fallbackReason: string | null = null,
) {
  return {
    items,
    next_cursor: null,
    search: {
      requested_mode: 'hybrid',
      effective_mode: fallbackReason ? 'keyword' : 'hybrid',
      fallback_reason: fallbackReason,
      index_coverage: 'partial',
      indexed_count: 1,
      eligible_count: 3,
      ranking_version: 'semantic-hybrid-v1',
    },
  }
}

function mockApi(
  options: {
    semanticBody?: ReturnType<typeof semantic>
    embeddingStates?: Record<string, string>
    semanticError?: { code: string; status: number }
  } = {},
) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = input.toString()
    if (path.includes('/spaces/') && path.includes('/discoveries'))
      return json({ items: [discovery], next_cursor: null })
    if (path.endsWith('/spaces') || path.includes('/spaces?'))
      return json({
        items: [{ id: 'space-1', name: 'Research', discovery_count: 1 }],
        next_cursor: null,
      })
    if (path.includes('/tags'))
      return json({
        items: [{ id: 'tag-1', name: 'Japan', discovery_count: 1 }],
        next_cursor: null,
      })
    if (path.includes('/embedding/status')) {
      const id = path.split('/discoveries/')[1].split('/')[0]
      return json(status(options.embeddingStates?.[id] ?? 'succeeded'))
    }
    if (path.includes('/embedding')) return json(status('succeeded'), 202)
    if (path.endsWith('/search/semantic')) {
      if (options.semanticError)
        return json(
          { error: { code: options.semanticError.code, message: 'Meaning search unavailable.' } },
          options.semanticError.status,
        )
      return json(options.semanticBody ?? semantic())
    }
    if (path.includes('/summary'))
      return json({
        status: 'unavailable',
        can_generate: false,
        key_points: [],
        topics: [],
        entities: [],
      })
    return json({ results: [discovery], total: 1, limit: 20, offset: 0 })
  })
}

async function chooseMeaning() {
  await userEvent.click(await screen.findByLabelText('Meaning'))
}

afterEach(() => vi.restoreAllMocks())

describe('Semantic Search UX', () => {
  it('keeps Keyword mode working and switches to explained Meaning mode without storage', async () => {
    const localSpy = vi.spyOn(Storage.prototype, 'setItem')
    const fetchMock = mockApi()
    render(<DiscoveryLibrary />)
    expect(await screen.findByLabelText('Keyword')).toBeChecked()
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'documentary')
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url.toString().includes('q=documentary'))).toBe(
        true,
      ),
    )
    await chooseMeaning()
    expect(screen.getByText(/Meaning search may send approved titles/)).toBeInTheDocument()
    expect(screen.getByText(/Notes, Tags, and Spaces are excluded/)).toBeInTheDocument()
    expect(localSpy).not.toHaveBeenCalled()
    expect(screen.queryByText(/\[0\./)).not.toBeInTheDocument()
  })

  it('validates, announces loading, renders results, partial coverage, no results, and no confidence', async () => {
    let resolveSearch: ((response: Response) => void) | undefined
    const fetchMock = mockApi()
    fetchMock.mockImplementationOnce(fetchMock.getMockImplementation()!)
    render(<DiscoveryLibrary />)
    await chooseMeaning()
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'a')
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('at least 2 characters'),
    )
    await userEvent.clear(screen.getByLabelText('Search Discoveries'))
    const original = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) => {
      if (input.toString().endsWith('/search/semantic'))
        return new Promise<Response>((resolve) => {
          resolveSearch = resolve
        })
      return original(input, init)
    })
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'abandoned town')
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Searching by meaning'),
    )
    resolveSearch?.(json(semantic()))
    expect(await screen.findByText(/1 of 3 eligible Discoveries indexed/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: discovery.custom_title })).toBeInTheDocument()

    fetchMock.mockImplementation((input, init) =>
      input.toString().endsWith('/search/semantic')
        ? Promise.resolve(json(semantic([], 'no_confident_semantic_match')))
        : original(input, init),
    )
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'x')
    expect(await screen.findByText(/no confident semantic match/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'No Discoveries match.' })).toBeInTheDocument()
  })

  it.each([
    ['feature_disabled', 'feature disabled'],
    ['provider_unavailable', 'provider unavailable'],
    ['provider_rate_limited', 'provider rate limited'],
    ['provider_timeout', 'provider timeout'],
  ])('shows keyword fallback for %s', async (reason, label) => {
    mockApi({ semanticBody: semantic([], reason) })
    render(<DiscoveryLibrary />)
    await chooseMeaning()
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'remember this')
    expect(await screen.findByText(new RegExp(label))).toBeInTheDocument()
    expect(screen.getByLabelText('Keyword')).toBeEnabled()
    expect(screen.queryByText(/api key|gemini-embedding|google error/i)).not.toBeInTheDocument()
  })

  it('passes Tag, Space, platform, favourite, and archive filters to meaning search', async () => {
    const fetchMock = mockApi()
    render(<DiscoveryLibrary />)
    await chooseMeaning()
    await userEvent.click(await screen.findByRole('button', { name: /Japan/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Research/ }))
    await userEvent.selectOptions(screen.getByLabelText('Platform'), 'youtube')
    await userEvent.click(screen.getByLabelText('Favourites'))
    await userEvent.click(screen.getByLabelText('Archived'))
    await userEvent.type(screen.getByLabelText('Search Discoveries'), 'vague memory')
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => url.toString().endsWith('/search/semantic')),
      ).toBe(true),
    )
    const request = [...fetchMock.mock.calls]
      .reverse()
      .find(([url]) => url.toString().endsWith('/search/semantic'))
    const body = JSON.parse(String((request?.[1] as RequestInit).body))
    expect(body.filters).toMatchObject({
      tag_id: 'tag-1',
      space_id: 'space-1',
      platform: ['youtube'],
      is_favourite: true,
      archive: 'archived',
    })
  })

  it('renders lifecycle states and performs index, retry, and stale re-index actions', async () => {
    const discoveries = [
      { ...discovery, id: 'new', custom_title: 'New item' },
      { ...discovery, id: 'pending', custom_title: 'Pending item' },
      { ...discovery, id: 'processing', custom_title: 'Processing item' },
      { ...discovery, id: 'indexed', custom_title: 'Indexed item' },
      { ...discovery, id: 'failed', custom_title: 'Failed item' },
      { ...discovery, id: 'stale', custom_title: 'Stale item' },
    ]
    const fetchMock = mockApi({
      embeddingStates: {
        new: 'unavailable',
        pending: 'pending',
        processing: 'processing',
        indexed: 'succeeded',
        failed: 'failed',
        stale: 'stale',
      },
    })
    const original = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) => {
      if (input.toString().includes('/discoveries?'))
        return Promise.resolve(
          json({ results: discoveries, total: discoveries.length, limit: 20, offset: 0 }),
        )
      if (input.toString().endsWith('/discoveries'))
        return Promise.resolve(
          json({ results: discoveries, total: discoveries.length, limit: 20, offset: 0 }),
        )
      return original(input, init)
    })
    render(<DiscoveryLibrary />)
    expect(await screen.findByText('Not indexed')).toBeInTheDocument()
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Indexed')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('Stale')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Index for search' }))
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await userEvent.click(screen.getByRole('button', { name: 'Re-index stale Discovery' }))
    expect(
      fetchMock.mock.calls.filter(([url]) => url.toString().includes('/embedding')).length,
    ).toBeGreaterThanOrEqual(9)
  })
})
