import { api } from '../../api/client'

export interface PublicUser {
  id: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Credentials {
  email: string
  password: string
}

export const register = (credentials: Credentials) =>
  api.post<PublicUser>('/api/v1/auth/register', credentials)
export const login = (credentials: Credentials) =>
  api.post<PublicUser>('/api/v1/auth/login', credentials)
export const logout = () => api.post<void>('/api/v1/auth/logout')
export const getCurrentUser = (signal?: AbortSignal) =>
  api.get<PublicUser>('/api/v1/users/me', signal)
