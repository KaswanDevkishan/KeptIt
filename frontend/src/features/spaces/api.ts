import { api } from '../../api/client'
import type { Discovery } from '../discoveries/api'

export interface Space {
  id: string
  name: string
  description: string | null
  discovery_count: number
  created_at: string
  updated_at: string
}

export interface SpaceInput {
  name: string
  description?: string | null
}

export interface SpacePage {
  items: Space[]
  next_cursor: string | null
}

export interface SpaceDiscoveryPage {
  items: Discovery[]
  next_cursor: string | null
}

export function listSpaces(signal?: AbortSignal) {
  return api.get<SpacePage>('/api/v1/spaces?limit=100&sort=name_asc', signal)
}

export function createSpace(input: SpaceInput) {
  return api.post<Space>('/api/v1/spaces', input)
}

export function updateSpace(id: string, input: Partial<SpaceInput>) {
  return api.patch<Space>(`/api/v1/spaces/${id}`, input)
}

export function deleteSpace(id: string) {
  return api.delete(`/api/v1/spaces/${id}`)
}

export function listSpaceDiscoveries(
  id: string,
  archive: 'active' | 'archived' | 'all' = 'active',
  signal?: AbortSignal,
) {
  return api.get<SpaceDiscoveryPage>(
    `/api/v1/spaces/${id}/discoveries?limit=100&archive=${archive}`,
    signal,
  )
}

export function addDiscoveryToSpace(spaceId: string, discoveryId: string) {
  return api.put(`/api/v1/spaces/${spaceId}/discoveries/${discoveryId}`)
}

export function removeDiscoveryFromSpace(spaceId: string, discoveryId: string) {
  return api.delete(`/api/v1/spaces/${spaceId}/discoveries/${discoveryId}`)
}
