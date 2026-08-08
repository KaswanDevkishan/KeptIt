import { api, apiRequest } from '../../api/client'

export const platforms = [
  'instagram',
  'youtube',
  'tiktok',
  'reddit',
  'x',
  'github',
  'generic_web',
] as const

export type Platform = (typeof platforms)[number]

export interface DiscoveryMetadata {
  status: 'pending' | 'processing' | 'succeeded' | 'failed' | 'unsupported'
  title: string | null
  description: string | null
  site_name: string | null
  creator_or_publisher: string | null
  thumbnail_url: string | null
  published_at: string | null
  fetched_at: string | null
  last_attempted_at: string | null
  failure_code: string | null
  failure_message_safe: string | null
  provider: string
  metadata_version: number
}

export interface Discovery {
  id: string
  original_url: string
  canonical_url: string
  platform: Platform
  custom_title: string | null
  personal_note: string | null
  save_reason: string | null
  is_favourite: boolean
  archived_at: string | null
  created_at: string
  updated_at: string
  display_title: string
  metadata: DiscoveryMetadata | null
  tags: { id: string; name: string }[]
}

export interface DiscoveryInput {
  url: string
  custom_title?: string | null
  personal_note?: string | null
  save_reason?: string | null
}

export interface DiscoveryUpdate {
  custom_title?: string | null
  personal_note?: string | null
  save_reason?: string | null
  is_favourite?: boolean
}

export interface DiscoveryFilters {
  q?: string
  platform?: Platform
  archived?: boolean
  favourite?: boolean
  limit?: number
  offset?: number
  tag_id?: string
  space_id?: string
}

export interface DiscoveryPage {
  results: Discovery[]
  total: number
  limit: number
  offset: number
}

export type EmbeddingStatusName =
  | 'unavailable'
  | 'pending'
  | 'processing'
  | 'succeeded'
  | 'failed'
  | 'unsupported'
  | 'stale'
export interface EmbeddingStatus {
  status: EmbeddingStatusName
  is_searchable: boolean
  generated_at: string | null
  last_attempted_at: string | null
  can_index: boolean
  can_retry: boolean
  retry_after_seconds: number | null
  error: { code: string; message: string } | null
}
export interface SemanticSearchResponse {
  items: { discovery: Discovery; relevance: { match_reasons: string[] } }[]
  next_cursor: string | null
  search: {
    effective_mode: string
    fallback_reason: string | null
    index_coverage: 'none' | 'partial' | 'complete'
    indexed_count: number
    eligible_count: number
  }
}

export type SummaryStatus =
  | 'unavailable'
  | 'pending'
  | 'processing'
  | 'succeeded'
  | 'failed'
  | 'unsupported'
  | 'insufficient_data'
  | 'stale'
export interface AiSummary {
  status: SummaryStatus
  availability_reason?: 'disabled' | 'provider_unavailable' | 'insufficient_data' | null
  summary: string | null
  key_points: string[]
  topics: string[]
  entities: { name: string; type: string }[]
  language: string | null
  confidence: number | null
  insufficiency_reason: string | null
  generated_at: string | null
  last_attempted_at: string | null
  is_regenerating: boolean
  can_generate: boolean
  can_retry: boolean
  can_regenerate: boolean
  retry_after_seconds: number | null
  error?: { code: string; message: string } | null
  last_attempt_error?: { code: string; message: string } | null
}

function idempotencyKey() {
  return `keptit-${crypto.randomUUID()}`
}
export function semanticSearch(query: string, filters: DiscoveryFilters, signal?: AbortSignal) {
  return apiRequest<SemanticSearchResponse>('/api/v1/search/semantic', {
    method: 'POST',
    signal,
    body: {
      query,
      mode: 'hybrid',
      filters: {
        platform: filters.platform ? [filters.platform] : [],
        space_id: filters.space_id ?? null,
        tag_id: filters.tag_id ?? null,
        is_favourite: filters.favourite ?? null,
        archive: filters.archived ? 'archived' : 'active',
      },
      limit: filters.limit ?? 20,
    },
  })
}
export function getEmbeddingStatus(id: string, signal?: AbortSignal) {
  return api.get<EmbeddingStatus>(`/api/v1/discoveries/${id}/embedding/status`, signal)
}
export function indexDiscovery(id: string) {
  return api.postWithHeaders<EmbeddingStatus>(
    `/api/v1/discoveries/${id}/embedding`,
    {},
    { 'Idempotency-Key': idempotencyKey() },
  )
}
export function retryEmbedding(id: string) {
  return api.postWithHeaders<EmbeddingStatus>(
    `/api/v1/discoveries/${id}/embedding/retry`,
    { confirm: true },
    { 'Idempotency-Key': idempotencyKey() },
  )
}
export function getSummary(id: string, signal?: AbortSignal) {
  return api.get<AiSummary>(`/api/v1/discoveries/${id}/summary`, signal)
}
export function generateSummary(id: string) {
  return api.postWithHeaders<AiSummary>(
    `/api/v1/discoveries/${id}/summary`,
    {},
    { 'Idempotency-Key': idempotencyKey() },
  )
}
export function retrySummary(id: string) {
  return generateSummary(id)
}
export function regenerateSummary(id: string) {
  return api.postWithHeaders<AiSummary>(
    `/api/v1/discoveries/${id}/summary/regenerate`,
    { confirm: true },
    { 'Idempotency-Key': idempotencyKey() },
  )
}
export function deleteSummary(id: string) {
  return api.delete(`/api/v1/discoveries/${id}/summary`)
}

export function createDiscovery(input: DiscoveryInput) {
  return api.post<Discovery>('/api/v1/discoveries', input)
}

export function listDiscoveries(filters: DiscoveryFilters = {}, signal?: AbortSignal) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const query = params.size ? `?${params}` : ''
  return api.get<DiscoveryPage>(`/api/v1/discoveries${query}`, signal)
}

export function getDiscovery(id: string) {
  return api.get<Discovery>(`/api/v1/discoveries/${id}`)
}

export function updateDiscovery(id: string, input: DiscoveryUpdate) {
  return api.patch<Discovery>(`/api/v1/discoveries/${id}`, input)
}

export function archiveDiscovery(id: string) {
  return api.post<Discovery>(`/api/v1/discoveries/${id}/archive`)
}

export function restoreDiscovery(id: string) {
  return api.post<Discovery>(`/api/v1/discoveries/${id}/restore`)
}

export function deleteDiscovery(id: string) {
  return api.delete(`/api/v1/discoveries/${id}`)
}

export function enrichDiscovery(id: string) {
  return api.post<Discovery>(`/api/v1/discoveries/${id}/enrich`)
}

export function detectPlatformLocally(value: string): Platform | null {
  try {
    const host = new URL(value).hostname.toLowerCase()
    if (host === 'instagram.com' || host === 'www.instagram.com') return 'instagram'
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'].includes(host))
      return 'youtube'
    if (host === 'tiktok.com' || host === 'www.tiktok.com') return 'tiktok'
    if (['reddit.com', 'www.reddit.com', 'old.reddit.com'].includes(host)) return 'reddit'
    if (['x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'].includes(host)) return 'x'
    if (host === 'github.com' || host === 'www.github.com') return 'github'
    return 'generic_web'
  } catch {
    return null
  }
}
