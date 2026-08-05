import { api } from '../../api/client'
import type { Discovery } from '../discoveries/api'

export interface TagSummary {
  id: string
  name: string
}
export interface Tag extends TagSummary {
  discovery_count: number
  created_at: string
  updated_at: string
}
export interface TagPage {
  items: Tag[]
  next_cursor: string | null
}
export interface TagDiscoveryPage {
  items: Discovery[]
  next_cursor: string | null
}

export function listTags(signal?: AbortSignal, q = '') {
  const search = q ? `&q=${encodeURIComponent(q)}` : ''
  return api.get<TagPage>(`/api/v1/tags?limit=100&sort=name_asc${search}`, signal)
}
export function getTag(id: string) {
  return api.get<Tag>(`/api/v1/tags/${id}`)
}
export function createTag(name: string) {
  return api.post<Tag>('/api/v1/tags', { name })
}
export function updateTag(id: string, name: string) {
  return api.patch<Tag>(`/api/v1/tags/${id}`, { name })
}
export function deleteTag(id: string) {
  return api.delete(`/api/v1/tags/${id}`)
}
export function listTagDiscoveries(
  id: string,
  archive: 'active' | 'archived' | 'all' = 'active',
  signal?: AbortSignal,
) {
  return api.get<TagDiscoveryPage>(
    `/api/v1/tags/${id}/discoveries?limit=100&archive=${archive}`,
    signal,
  )
}
export function attachTagToDiscovery(tagId: string, discoveryId: string) {
  return api.put(`/api/v1/tags/${tagId}/discoveries/${discoveryId}`)
}
export function detachTagFromDiscovery(tagId: string, discoveryId: string) {
  return api.delete(`/api/v1/tags/${tagId}/discoveries/${discoveryId}`)
}
