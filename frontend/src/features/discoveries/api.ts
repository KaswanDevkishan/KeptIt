import { api } from '../../api/client'

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
}

export interface DiscoveryPage {
  results: Discovery[]
  total: number
  limit: number
  offset: number
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
