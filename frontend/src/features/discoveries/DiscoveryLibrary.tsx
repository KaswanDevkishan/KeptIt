import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../../api/client'
import * as spaceApi from '../spaces/api'
import type { Space } from '../spaces/api'
import * as tagApi from '../tags/api'
import type { Tag } from '../tags/api'
import * as discoveryApi from './api'
import type { Discovery, DiscoveryInput, Platform } from './api'

const emptyInput: DiscoveryInput = { url: '', custom_title: '', personal_note: '', save_reason: '' }

function titleFor(discovery: Discovery) {
  if (discovery.custom_title) return discovery.custom_title
  if (discovery.metadata?.title) return discovery.metadata.title
  try {
    return new URL(discovery.original_url).hostname.replace(/^www\./, '')
  } catch {
    return discovery.original_url
  }
}

function AiSummaryPanel({ discovery }: { discovery: Discovery }) {
  const [summary, setSummary] = useState<discoveryApi.AiSummary | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async () => {
    try {
      const result = await discoveryApi.getSummary(discovery.id)
      if (
        ![
          'unavailable',
          'pending',
          'processing',
          'succeeded',
          'failed',
          'unsupported',
          'insufficient_data',
          'stale',
        ].includes(result.status)
      )
        return
      setSummary({
        ...result,
        key_points: result.key_points ?? [],
        topics: result.topics ?? [],
        entities: result.entities ?? [],
      })
      setError('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'AI summary is unavailable.')
    }
  }, [discovery.id])
  useEffect(() => {
    void refresh()
  }, [refresh])
  useEffect(() => {
    if (!summary || !['pending', 'processing'].includes(summary.status) || summary.is_regenerating)
      return
    const timer = window.setInterval(() => void refresh(), 1500)
    return () => window.clearInterval(timer)
  }, [refresh, summary])
  async function act(action: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try {
      await action()
      await refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'AI summary action failed.')
    } finally {
      setBusy(false)
    }
  }
  if (!summary && !error)
    return (
      <section className="ai-summary" aria-label="AI summary">
        <p role="status">Loading AI summary…</p>
      </section>
    )
  if (error && !summary) return null
  if (!summary) return null
  return (
    <section className="ai-summary" aria-label="AI-generated summary">
      <div className="ai-summary__heading">
        <strong>AI-generated summary</strong>
        {summary.status === 'stale' && <span>Source metadata changed</span>}
      </div>
      {summary.status === 'unavailable' &&
        (summary.can_generate ? (
          <button
            disabled={busy}
            onClick={() => void act(() => discoveryApi.generateSummary(discovery.id))}
          >
            Generate AI summary
          </button>
        ) : (
          <p>AI summary is unavailable.</p>
        ))}
      {['pending', 'processing'].includes(summary.status) && (
        <p role="status">Generating summary…</p>
      )}
      {summary.summary && <p>{summary.summary}</p>}
      {summary.key_points.length > 0 && (
        <>
          <h3>Key points</h3>
          <ul>
            {summary.key_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </>
      )}
      {summary.topics.length > 0 && (
        <p>
          <strong>Topics:</strong> {summary.topics.join(', ')}
        </p>
      )}
      {summary.entities.length > 0 && (
        <p>
          <strong>Entities:</strong> {summary.entities.map((entity) => entity.name).join(', ')}
        </p>
      )}
      {summary.status === 'insufficient_data' && (
        <p>
          {summary.insufficiency_reason ??
            'There is not enough source metadata to summarize reliably.'}
        </p>
      )}
      {summary.status === 'unsupported' && (
        <p>This source is not supported by the summary metadata policy.</p>
      )}
      {summary.status === 'failed' && (
        <p role="alert">AI summary generation failed. Your Discovery is unchanged.</p>
      )}
      {error && <p role="alert">{error}</p>}
      <div className="ai-summary__actions">
        {summary.can_retry && (
          <button
            disabled={busy}
            onClick={() => void act(() => discoveryApi.retrySummary(discovery.id))}
          >
            Retry
          </button>
        )}
        {summary.can_regenerate && (
          <button
            disabled={busy || summary.is_regenerating}
            onClick={() => {
              if (
                window.confirm(
                  'Regenerate this AI summary? The current summary stays visible until replacement succeeds.',
                )
              )
                void act(() => discoveryApi.regenerateSummary(discovery.id))
            }}
          >
            Regenerate
          </button>
        )}
        {summary.status !== 'unavailable' && (
          <button
            disabled={busy}
            onClick={() => {
              if (window.confirm('Delete this AI-generated summary?'))
                void act(async () => {
                  await discoveryApi.deleteSummary(discovery.id)
                  await refresh()
                })
            }}
          >
            Delete summary
          </button>
        )}
      </div>
    </section>
  )
}

function DiscoveryForm({
  initial = emptyInput,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: DiscoveryInput
  submitLabel: string
  onSubmit: (input: DiscoveryInput) => Promise<void>
  onCancel: () => void
}) {
  const [input, setInput] = useState(initial)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const preview = discoveryApi.detectPlatformLocally(input.url)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    if (!initial.url) {
      try {
        const url = new URL(input.url)
        if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error()
      } catch {
        setError('Enter a valid HTTP or HTTPS URL.')
        return
      }
    }
    setSaving(true)
    try {
      await onSubmit(input)
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Something went wrong. Please try again.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="discovery-form" onSubmit={(event) => void submit(event)}>
      {!initial.url && (
        <label>
          URL
          <input
            autoFocus
            required
            type="url"
            value={input.url}
            onChange={(event) => setInput({ ...input, url: event.target.value })}
            placeholder="https://example.com/something-worth-keeping"
          />
        </label>
      )}
      {preview && !initial.url && (
        <p className="platform-preview">Platform: {preview.replace('_', ' ')}</p>
      )}
      <label>
        Custom title <span>Optional</span>
        <input
          maxLength={300}
          value={input.custom_title ?? ''}
          onChange={(event) => setInput({ ...input, custom_title: event.target.value })}
        />
      </label>
      <label>
        Personal note <span>Optional</span>
        <textarea
          maxLength={10000}
          rows={3}
          value={input.personal_note ?? ''}
          onChange={(event) => setInput({ ...input, personal_note: event.target.value })}
        />
      </label>
      <label>
        Why are you saving this? <span>Optional</span>
        <input
          maxLength={500}
          value={input.save_reason ?? ''}
          onChange={(event) => setInput({ ...input, save_reason: event.target.value })}
        />
      </label>
      {error && (
        <p className="form-alert" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button className="button button--quiet" type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="button button--primary" disabled={saving} type="submit">
          {saving ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

function SpaceForm({
  title,
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  title: string
  initial?: Space
  submitLabel: string
  onSubmit: (input: spaceApi.SpaceInput) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Enter a Space name.')
      return
    }
    if ([...trimmed].length > 100) {
      setError('Space names must be 100 characters or fewer.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSubmit({ name, description: description || null })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not save this Space.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="space-title">
        <h2 id="space-title">{title}</h2>
        <form className="discovery-form" onSubmit={(event) => void submit(event)}>
          <label>
            Space name
            <input
              autoFocus
              required
              maxLength={100}
              value={name}
              aria-invalid={Boolean(error)}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            Description <span>Optional</span>
            <textarea
              maxLength={500}
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          {error && (
            <p className="form-alert" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button className="button button--quiet" type="button" onClick={onCancel}>
              Cancel
            </button>
            <button className="button button--primary" disabled={saving} type="submit">
              {saving ? 'Saving…' : submitLabel}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

function TagForm({
  title,
  initial,
  onSubmit,
  onCancel,
}: {
  title: string
  initial?: Tag
  onSubmit: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || [...trimmed].length > 50) {
      setError('Tag names must contain 1 to 50 characters.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSubmit(name)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not save this Tag.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tag-dialog-title"
      >
        <h2 id="tag-dialog-title">{title}</h2>
        <form className="discovery-form" onSubmit={(event) => void submit(event)}>
          <label>
            Tag name
            <input
              autoFocus
              required
              maxLength={50}
              value={name}
              aria-invalid={Boolean(error)}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <p className="field-help">1–50 characters. Tags describe what a Discovery is about.</p>
          {error && (
            <p className="form-alert" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button className="button button--quiet" type="button" onClick={onCancel}>
              Cancel
            </button>
            <button className="button button--primary" disabled={saving} type="submit">
              {saving ? 'Saving…' : initial ? 'Save changes' : 'Create Tag'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

export function DiscoveryLibrary() {
  const [page, setPage] = useState<discoveryApi.DiscoveryPage | null>(null)
  const [error, setError] = useState('')
  const [showSave, setShowSave] = useState(false)
  const [editing, setEditing] = useState<Discovery | null>(null)
  const [q, setQ] = useState('')
  const [platform, setPlatform] = useState<Platform | ''>('')
  const [archived, setArchived] = useState(false)
  const [favourite, setFavourite] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [spaces, setSpaces] = useState<Space[]>([])
  const [spacesLoading, setSpacesLoading] = useState(true)
  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(null)
  const [spaceDialog, setSpaceDialog] = useState<'create' | 'rename' | 'delete' | null>(null)
  const [editingSpace, setEditingSpace] = useState<Space | null>(null)
  const [memberships, setMemberships] = useState<Record<string, Set<string>>>({})
  const [membershipBusy, setMembershipBusy] = useState<string | null>(null)
  const [tags, setTags] = useState<Tag[]>([])
  const [tagsLoading, setTagsLoading] = useState(true)
  const [tagSearch, setTagSearch] = useState('')
  const [selectedTagId, setSelectedTagId] = useState<string | null>(null)
  const [tagDialog, setTagDialog] = useState<'create' | 'rename' | 'delete' | null>(null)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [tagMembershipBusy, setTagMembershipBusy] = useState<string | null>(null)

  const loadTags = useCallback(async (signal?: AbortSignal) => {
    setTagsLoading(true)
    try {
      const result = await tagApi.listTags(signal)
      setTags(Array.isArray(result.items) ? result.items : [])
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === 'AbortError'))
        setError(caught instanceof ApiError ? caught.message : 'Could not load your Tags.')
    } finally {
      setTagsLoading(false)
    }
  }, [])

  const loadSpaces = useCallback(async (signal?: AbortSignal) => {
    setSpacesLoading(true)
    try {
      const result = await spaceApi.listSpaces(signal)
      const items = Array.isArray(result.items) ? result.items : []
      setSpaces(items)
      const entries = await Promise.all(
        items.map(async (space) => {
          const contents = await spaceApi.listSpaceDiscoveries(space.id, 'all', signal)
          return [space.id, new Set(contents.items.map((item) => item.id))] as const
        }),
      )
      setMemberships(Object.fromEntries(entries))
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      setError(caught instanceof ApiError ? caught.message : 'Could not load your Spaces.')
    } finally {
      setSpacesLoading(false)
    }
  }, [])

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setError('')
        if (selectedSpaceId && !selectedTagId) {
          const spacePage = await spaceApi.listSpaceDiscoveries(
            selectedSpaceId,
            archived ? 'archived' : 'active',
            signal,
          )
          const term = q.trim().toLocaleLowerCase()
          const results = spacePage.items.filter(
            (item) =>
              (!term ||
                [item.display_title, item.personal_note, item.original_url].some((value) =>
                  value?.toLocaleLowerCase().includes(term),
                )) &&
              (!platform || item.platform === platform) &&
              (!favourite || item.is_favourite),
          )
          setPage({ results, total: results.length, limit: 100, offset: 0 })
        } else {
          setPage(
            await discoveryApi.listDiscoveries(
              {
                q,
                platform: platform || undefined,
                archived,
                favourite: favourite || undefined,
                space_id: selectedSpaceId ?? undefined,
                tag_id: selectedTagId ?? undefined,
              },
              signal,
            ),
          )
        }
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === 'AbortError') return
        setError(caught instanceof ApiError ? caught.message : 'Could not load your library.')
      }
    },
    [archived, favourite, platform, q, selectedSpaceId, selectedTagId],
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadSpaces(controller.signal)
    return () => controller.abort()
  }, [loadSpaces])

  useEffect(() => {
    const controller = new AbortController()
    void loadTags(controller.signal)
    return () => controller.abort()
  }, [loadTags])

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => void load(controller.signal), 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [load])

  async function mutate(action: () => Promise<unknown>, message: string) {
    try {
      await action()
      setFeedback(message)
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'That action could not be completed.')
    }
  }

  const hasFilters = Boolean(q || platform || archived || favourite || selectedTagId)
  const selectedSpace = spaces.find((space) => space.id === selectedSpaceId) ?? null
  const selectedTag = tags.find((tag) => tag.id === selectedTagId) ?? null

  async function saveTag(name: string) {
    if (tagDialog === 'rename' && editingTag) {
      await tagApi.updateTag(editingTag.id, name)
      setFeedback('Tag renamed.')
    } else {
      await tagApi.createTag(name)
      setFeedback('Tag created.')
    }
    setTagDialog(null)
    setEditingTag(null)
    await loadTags()
    await load()
  }

  async function confirmDeleteTag() {
    if (!editingTag) return
    try {
      await tagApi.deleteTag(editingTag.id)
      if (selectedTagId === editingTag.id) setSelectedTagId(null)
      setFeedback('Tag deleted. Your Discoveries remain in your library.')
      setTagDialog(null)
      setEditingTag(null)
      await loadTags()
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not delete this Tag.')
    }
  }

  async function toggleTag(tag: Tag, discovery: Discovery, assigned: boolean) {
    const key = `${tag.id}:${discovery.id}`
    setTagMembershipBusy(key)
    try {
      if (assigned) await tagApi.detachTagFromDiscovery(tag.id, discovery.id)
      else await tagApi.attachTagToDiscovery(tag.id, discovery.id)
      setFeedback(assigned ? `Removed ${tag.name}.` : `Added ${tag.name}.`)
      await loadTags()
      await load()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not update Tags.')
      await load()
    } finally {
      setTagMembershipBusy(null)
    }
  }

  async function saveSpace(input: spaceApi.SpaceInput) {
    if (spaceDialog === 'rename' && editingSpace) {
      await spaceApi.updateSpace(editingSpace.id, input)
      setFeedback('Space renamed.')
    } else {
      await spaceApi.createSpace(input)
      setFeedback('Space created.')
    }
    setSpaceDialog(null)
    setEditingSpace(null)
    await loadSpaces()
  }

  async function confirmDeleteSpace() {
    if (!editingSpace) return
    try {
      await spaceApi.deleteSpace(editingSpace.id)
      if (selectedSpaceId === editingSpace.id) setSelectedSpaceId(null)
      setFeedback('Space deleted. Your Discoveries remain in your library.')
      setSpaceDialog(null)
      setEditingSpace(null)
      await loadSpaces()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not delete this Space.')
    }
  }

  async function toggleMembership(space: Space, discovery: Discovery, assigned: boolean) {
    const key = `${space.id}:${discovery.id}`
    setMembershipBusy(key)
    setMemberships((current) => {
      const next = { ...current, [space.id]: new Set(current[space.id] ?? []) }
      if (assigned) next[space.id].delete(discovery.id)
      else next[space.id].add(discovery.id)
      return next
    })
    try {
      if (assigned) await spaceApi.removeDiscoveryFromSpace(space.id, discovery.id)
      else await spaceApi.addDiscoveryToSpace(space.id, discovery.id)
      setFeedback(assigned ? `Removed from ${space.name}.` : `Added to ${space.name}.`)
      await loadSpaces()
      if (selectedSpaceId) await load()
    } catch (caught) {
      await loadSpaces()
      setError(caught instanceof ApiError ? caught.message : 'Could not update Spaces.')
    } finally {
      setMembershipBusy(null)
    }
  }

  return (
    <section className="library-layout" aria-label="Discovery library">
      <aside className="spaces-sidebar" aria-labelledby="spaces-title">
        <div className="spaces-sidebar__heading">
          <h2 id="spaces-title">My Spaces</h2>
          <button className="text-button" onClick={() => setSpaceDialog('create')}>
            Create Space
          </button>
        </div>
        <nav aria-label="Library views">
          <button
            className={!selectedSpaceId && !archived ? 'active' : ''}
            onClick={() => {
              setSelectedSpaceId(null)
              setArchived(false)
            }}
          >
            All Discoveries
          </button>
          <button
            className={!selectedSpaceId && archived ? 'active' : ''}
            onClick={() => {
              setSelectedSpaceId(null)
              setArchived(true)
            }}
          >
            Archive
          </button>
          {spacesLoading && <span className="spaces-loading">Loading Spaces…</span>}
          {spaces.map((space) => (
            <button
              className={selectedSpaceId === space.id ? 'active' : ''}
              key={space.id}
              onClick={() => setSelectedSpaceId(space.id)}
            >
              <span>{space.name}</span>
              <span aria-label={`${space.discovery_count} Discoveries`}>
                {space.discovery_count}
              </span>
            </button>
          ))}
        </nav>
        <div className="tags-sidebar" aria-labelledby="tags-title">
          <div className="spaces-sidebar__heading">
            <h2 id="tags-title">Tags</h2>
            <button className="text-button" onClick={() => setTagDialog('create')}>
              Create Tag
            </button>
          </div>
          <label className="tag-search">
            Search Tags
            <input
              aria-label="Search Tags"
              value={tagSearch}
              onChange={(event) => setTagSearch(event.target.value)}
            />
          </label>
          {tagsLoading && <span className="spaces-loading">Loading Tags…</span>}
          {!tagsLoading && tags.length === 0 && (
            <p className="sidebar-empty">No Tags yet. Tags describe subjects across Spaces.</p>
          )}
          <nav aria-label="Tag filters">
            {tags
              .filter((tag) =>
                tag.name.toLocaleLowerCase().includes(tagSearch.trim().toLocaleLowerCase()),
              )
              .map((tag) => (
                <button
                  className={selectedTagId === tag.id ? 'active' : ''}
                  key={tag.id}
                  title={tag.name}
                  onClick={() => setSelectedTagId(tag.id)}
                >
                  <span>{tag.name}</span>
                  <span aria-label={`${tag.discovery_count} Discoveries`}>
                    {tag.discovery_count}
                  </span>
                </button>
              ))}
          </nav>
        </div>
      </aside>
      <div className="library" aria-labelledby="library-title">
        <div className="library-heading">
          <div>
            <p className="eyebrow">Private library</p>
            <h1 id="library-title">
              {selectedSpace?.name ?? 'Your Discoveries'}
              {selectedTag ? ` · ${selectedTag.name}` : ''}
            </h1>
            {selectedSpace?.description && <p>{selectedSpace.description}</p>}
          </div>
          <div className="library-heading__actions">
            {selectedSpace && (
              <>
                <button
                  className="button button--quiet"
                  onClick={() => {
                    setEditingSpace(selectedSpace)
                    setSpaceDialog('rename')
                  }}
                >
                  Rename Space
                </button>
                <button
                  className="button button--danger"
                  onClick={() => {
                    setEditingSpace(selectedSpace)
                    setSpaceDialog('delete')
                  }}
                >
                  Delete Space
                </button>
              </>
            )}
            {selectedTag && (
              <>
                <button className="button button--quiet" onClick={() => setSelectedTagId(null)}>
                  Clear Tag filter
                </button>
                <button
                  className="button button--quiet"
                  onClick={() => {
                    setEditingTag(selectedTag)
                    setTagDialog('rename')
                  }}
                >
                  Rename Tag
                </button>
                <button
                  className="button button--danger"
                  onClick={() => {
                    setEditingTag(selectedTag)
                    setTagDialog('delete')
                  }}
                >
                  Delete Tag
                </button>
              </>
            )}
            <button className="button button--primary" onClick={() => setShowSave(true)}>
              Save Discovery
            </button>
          </div>
        </div>
        <div className="library-filters" aria-label="Library filters">
          <label className="search-field">
            Search
            <input
              aria-label="Search Discoveries"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Title, note, or URL"
            />
          </label>
          <label>
            Platform
            <select value={platform} onChange={(e) => setPlatform(e.target.value as Platform | '')}>
              <option value="">All platforms</option>
              {discoveryApi.platforms.map((value) => (
                <option key={value} value={value}>
                  {value.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <label className="check-filter">
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.target.checked)}
            />
            Archived
          </label>
          <label className="check-filter">
            <input
              type="checkbox"
              checked={favourite}
              onChange={(e) => setFavourite(e.target.checked)}
            />
            Favourites
          </label>
          {hasFilters && (
            <button
              className="text-button"
              onClick={() => {
                setQ('')
                setPlatform('')
                setArchived(false)
                setFavourite(false)
                setSelectedTagId(null)
              }}
            >
              Clear filters
            </button>
          )}
        </div>
        {feedback && (
          <p className="success-banner" role="status">
            {feedback}
          </p>
        )}
        {error && (
          <p className="form-alert" role="alert">
            {error}
          </p>
        )}
        {page === null && !error && <p className="library-message">Loading your library…</p>}
        {page?.results.length === 0 && (
          <div className="empty-library">
            <p className="eyebrow">A fresh start</p>
            <h2>
              {selectedTag
                ? 'No discoveries with this Tag.'
                : selectedSpace && !hasFilters
                  ? 'No discoveries in this space.'
                  : hasFilters
                    ? 'No Discoveries match.'
                    : 'Keep what matters.'}
            </h2>
            <p>
              {selectedTag
                ? 'Clear the Tag filter or change your other filters.'
                : selectedSpace && !hasFilters
                  ? 'Add Discoveries from their card’s Spaces menu. Nothing has been deleted.'
                  : hasFilters
                    ? 'Try clearing or changing your filters.'
                    : 'Save useful, entertaining, or inspiring URLs with the context you want to remember.'}
            </p>
            {!hasFilters && (
              <button className="button button--primary" onClick={() => setShowSave(true)}>
                Save your first Discovery
              </button>
            )}
            {selectedTag && (
              <button className="button button--quiet" onClick={() => setSelectedTagId(null)}>
                Clear Tag filter
              </button>
            )}
          </div>
        )}
        {page && page.results.length > 0 && (
          <p className="result-count">
            {page.total} {page.total === 1 ? 'Discovery' : 'Discoveries'}
          </p>
        )}
        <div className="discovery-grid">
          {page?.results.map((discovery) => (
            <article className="discovery-card" key={discovery.id}>
              {discovery.metadata?.thumbnail_url && (
                <div className="discovery-thumbnail">
                  <img
                    src={discovery.metadata.thumbnail_url}
                    alt=""
                    loading="lazy"
                    referrerPolicy="no-referrer"
                    onError={(event) => {
                      event.currentTarget.hidden = true
                    }}
                  />
                </div>
              )}
              <div className="discovery-card__meta">
                <span className="platform-badge">{discovery.platform.replace('_', ' ')}</span>
                <time dateTime={discovery.created_at}>
                  Saved {new Date(discovery.created_at).toLocaleDateString()}
                </time>
              </div>
              <h2>
                <a href={discovery.original_url} target="_blank" rel="noreferrer">
                  {titleFor(discovery)}
                </a>
              </h2>
              <p className="discovery-url">{discovery.original_url}</p>
              {discovery.metadata?.description && (
                <p className="metadata-description">{discovery.metadata.description}</p>
              )}
              {(discovery.metadata?.site_name || discovery.metadata?.creator_or_publisher) && (
                <p className="metadata-source">
                  {[discovery.metadata.site_name, discovery.metadata.creator_or_publisher]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
              {discovery.metadata?.status === 'pending' && (
                <div className="metadata-status" role="status">
                  <span>Source details pending.</span>{' '}
                  <button
                    className="text-button"
                    onClick={() =>
                      void mutate(
                        () => discoveryApi.enrichDiscovery(discovery.id),
                        'Source details added.',
                      )
                    }
                  >
                    Add source details
                  </button>
                </div>
              )}
              {discovery.metadata?.status === 'processing' && (
                <p className="metadata-status" role="status">
                  Refreshing source details…
                </p>
              )}
              {['failed', 'unsupported'].includes(discovery.metadata?.status ?? '') && (
                <div className="metadata-status metadata-status--failed">
                  <span>Source details unavailable.</span>
                  <button
                    className="text-button"
                    onClick={() =>
                      void mutate(
                        () => discoveryApi.enrichDiscovery(discovery.id),
                        'Source details refreshed.',
                      )
                    }
                  >
                    Retry metadata
                  </button>
                </div>
              )}
              <AiSummaryPanel discovery={discovery} />
              {discovery.personal_note && <p className="note-preview">{discovery.personal_note}</p>}
              {discovery.save_reason && <p className="save-reason">Why: {discovery.save_reason}</p>}
              {discovery.tags?.length > 0 && (
                <div className="tag-chips" aria-label="Tags">
                  {discovery.tags.slice(0, 3).map((tag) => (
                    <button key={tag.id} title={tag.name} onClick={() => setSelectedTagId(tag.id)}>
                      {tag.name}
                    </button>
                  ))}
                  {discovery.tags.length > 3 && (
                    <span aria-label={`${discovery.tags.length - 3} more Tags`}>
                      +{discovery.tags.length - 3}
                    </span>
                  )}
                </div>
              )}
              {spaces.some((space) => memberships[space.id]?.has(discovery.id)) && (
                <p className="space-badges">
                  Spaces:{' '}
                  {spaces
                    .filter((space) => memberships[space.id]?.has(discovery.id))
                    .map((space) => space.name)
                    .join(', ')}
                </p>
              )}
              <details className="space-picker">
                <summary>Add or remove Spaces</summary>
                {spaces.length === 0 ? (
                  <p>No Spaces yet. Create one from the sidebar.</p>
                ) : (
                  spaces.map((space) => {
                    const assigned = memberships[space.id]?.has(discovery.id) ?? false
                    const busy = membershipBusy === `${space.id}:${discovery.id}`
                    return (
                      <label key={space.id}>
                        <input
                          type="checkbox"
                          checked={assigned}
                          disabled={busy}
                          onChange={() => void toggleMembership(space, discovery, assigned)}
                        />
                        {space.name}
                      </label>
                    )
                  })
                )}
              </details>
              <details className="space-picker tag-picker">
                <summary>Add or remove Tags</summary>
                {tags.length === 0 ? (
                  <p>
                    No Tags yet.{' '}
                    <button className="text-button" onClick={() => setTagDialog('create')}>
                      Create a Tag
                    </button>
                  </p>
                ) : (
                  tags.map((tag) => {
                    const assigned = discovery.tags?.some((item) => item.id === tag.id) ?? false
                    const busy = tagMembershipBusy === `${tag.id}:${discovery.id}`
                    return (
                      <label key={tag.id} title={tag.name}>
                        <input
                          type="checkbox"
                          checked={assigned}
                          disabled={busy || (!assigned && discovery.tags.length >= 20)}
                          onChange={() => void toggleTag(tag, discovery, assigned)}
                        />
                        {tag.name}
                      </label>
                    )
                  })
                )}
              </details>
              <div className="card-actions">
                <button
                  aria-label={`${discovery.is_favourite ? 'Unfavourite' : 'Favourite'} ${titleFor(discovery)}`}
                  onClick={() =>
                    void mutate(
                      () =>
                        discoveryApi.updateDiscovery(discovery.id, {
                          is_favourite: !discovery.is_favourite,
                        }),
                      discovery.is_favourite ? 'Removed from favourites.' : 'Added to favourites.',
                    )
                  }
                >
                  {discovery.is_favourite ? '★ Favourited' : '☆ Favourite'}
                </button>
                <button onClick={() => setEditing(discovery)}>Edit</button>
                <button
                  onClick={() =>
                    void mutate(
                      () =>
                        discovery.archived_at
                          ? discoveryApi.restoreDiscovery(discovery.id)
                          : discoveryApi.archiveDiscovery(discovery.id),
                      discovery.archived_at ? 'Discovery restored.' : 'Discovery archived.',
                    )
                  }
                >
                  {discovery.archived_at ? 'Restore' : 'Archive'}
                </button>
                <button
                  className="danger-action"
                  onClick={() => {
                    if (window.confirm('Permanently delete this Discovery? This cannot be undone.'))
                      void mutate(
                        () => discoveryApi.deleteDiscovery(discovery.id),
                        'Discovery permanently deleted.',
                      )
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
        {(showSave || editing) && (
          <div className="dialog-backdrop" role="presentation">
            <section
              className="dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="discovery-dialog-title"
            >
              <h2 id="discovery-dialog-title">{editing ? 'Edit Discovery' : 'Save Discovery'}</h2>
              <DiscoveryForm
                initial={
                  editing
                    ? {
                        url: editing.original_url,
                        custom_title: editing.custom_title,
                        personal_note: editing.personal_note,
                        save_reason: editing.save_reason,
                      }
                    : undefined
                }
                submitLabel={editing ? 'Save changes' : 'Save Discovery'}
                onCancel={() => {
                  setShowSave(false)
                  setEditing(null)
                }}
                onSubmit={async (input) => {
                  if (editing)
                    await discoveryApi.updateDiscovery(editing.id, {
                      custom_title: input.custom_title || null,
                      personal_note: input.personal_note || null,
                      save_reason: input.save_reason || null,
                    })
                  else await discoveryApi.createDiscovery(input)
                  setShowSave(false)
                  setEditing(null)
                  setFeedback(
                    editing
                      ? 'Discovery updated.'
                      : 'Discovery saved. Source details can be added separately.',
                  )
                  await load()
                }}
              />
            </section>
          </div>
        )}
        {spaceDialog === 'create' && (
          <SpaceForm
            title="Create Space"
            submitLabel="Create"
            onSubmit={saveSpace}
            onCancel={() => setSpaceDialog(null)}
          />
        )}
        {spaceDialog === 'rename' && editingSpace && (
          <SpaceForm
            title="Rename Space"
            initial={editingSpace}
            submitLabel="Save changes"
            onSubmit={saveSpace}
            onCancel={() => {
              setSpaceDialog(null)
              setEditingSpace(null)
            }}
          />
        )}
        {spaceDialog === 'delete' && editingSpace && (
          <div className="dialog-backdrop" role="presentation">
            <section
              className="dialog"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="delete-space-title"
            >
              <h2 id="delete-space-title">Delete {editingSpace.name}?</h2>
              <p>Deleting a Space does NOT delete Discoveries. They remain in your library.</p>
              <div className="form-actions">
                <button className="button button--quiet" onClick={() => setSpaceDialog(null)}>
                  Cancel
                </button>
                <button className="button button--danger" onClick={() => void confirmDeleteSpace()}>
                  Delete Space
                </button>
              </div>
            </section>
          </div>
        )}
        {tagDialog === 'create' && (
          <TagForm title="Create Tag" onSubmit={saveTag} onCancel={() => setTagDialog(null)} />
        )}
        {tagDialog === 'rename' && editingTag && (
          <TagForm
            title="Rename Tag"
            initial={editingTag}
            onSubmit={saveTag}
            onCancel={() => {
              setTagDialog(null)
              setEditingTag(null)
            }}
          />
        )}
        {tagDialog === 'delete' && editingTag && (
          <div className="dialog-backdrop" role="presentation">
            <section
              className="dialog"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="delete-tag-title"
            >
              <h2 id="delete-tag-title">Delete {editingTag.name}?</h2>
              <p>
                The Tag will be permanently deleted. Discoveries will not be deleted. The Tag will
                be removed from attached Discoveries.
              </p>
              <div className="form-actions">
                <button className="button button--quiet" onClick={() => setTagDialog(null)}>
                  Cancel
                </button>
                <button className="button button--danger" onClick={() => void confirmDeleteTag()}>
                  Delete Tag
                </button>
              </div>
            </section>
          </div>
        )}
      </div>
    </section>
  )
}
