import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../../api/client'
import * as discoveryApi from './api'
import type { Discovery, DiscoveryInput, Platform } from './api'

const emptyInput: DiscoveryInput = { url: '', custom_title: '', personal_note: '', save_reason: '' }

function titleFor(discovery: Discovery) {
  if (discovery.custom_title) return discovery.custom_title
  try {
    return new URL(discovery.original_url).hostname.replace(/^www\./, '')
  } catch {
    return discovery.original_url
  }
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

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setError('')
        setPage(
          await discoveryApi.listDiscoveries(
            { q, platform: platform || undefined, archived, favourite: favourite || undefined },
            signal,
          ),
        )
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === 'AbortError') return
        setError(caught instanceof ApiError ? caught.message : 'Could not load your library.')
      }
    },
    [archived, favourite, platform, q],
  )

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

  const hasFilters = Boolean(q || platform || archived || favourite)

  return (
    <section className="library" aria-labelledby="library-title">
      <div className="library-heading">
        <div>
          <p className="eyebrow">Private library</p>
          <h1 id="library-title">Your Discoveries</h1>
        </div>
        <button className="button button--primary" onClick={() => setShowSave(true)}>
          Save Discovery
        </button>
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
          <h2>{hasFilters ? 'No Discoveries match.' : 'Keep what matters.'}</h2>
          <p>
            {hasFilters
              ? 'Try clearing or changing your filters.'
              : 'Save useful, entertaining, or inspiring URLs with the context you want to remember.'}
          </p>
          {!hasFilters && (
            <button className="button button--primary" onClick={() => setShowSave(true)}>
              Save your first Discovery
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
            {discovery.personal_note && <p className="note-preview">{discovery.personal_note}</p>}
            {discovery.save_reason && <p className="save-reason">Why: {discovery.save_reason}</p>}
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
                setFeedback(editing ? 'Discovery updated.' : 'Discovery saved.')
                await load()
              }}
            />
          </section>
        </div>
      )}
    </section>
  )
}
