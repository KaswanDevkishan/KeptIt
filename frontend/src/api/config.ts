export function resolveApiBaseUrl(configuredUrl: string | undefined, production: boolean): string {
  const value = configuredUrl?.trim()
  if (!value) {
    if (production) throw new Error('VITE_API_BASE_URL is required for production builds.')
    return 'http://localhost:8000'
  }

  const parsed = new URL(value)
  if (production && parsed.protocol !== 'https:') {
    throw new Error('VITE_API_BASE_URL must use HTTPS in production.')
  }
  if (production && ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname)) {
    throw new Error('VITE_API_BASE_URL must not use localhost in production.')
  }
  if (
    parsed.username ||
    parsed.password ||
    (parsed.pathname !== '' && !/^\/+$/u.test(parsed.pathname)) ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error('VITE_API_BASE_URL must be a plain backend origin.')
  }
  return value.replace(/\/+$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.PROD,
)
