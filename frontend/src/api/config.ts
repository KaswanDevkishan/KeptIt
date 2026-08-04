const configuredApiUrl = import.meta.env.VITE_API_BASE_URL as string | undefined

export const API_BASE_URL = (configuredApiUrl ?? 'http://localhost:8000').replace(/\/$/, '')
