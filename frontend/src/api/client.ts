import { API_BASE_URL } from './config'

type Method = 'GET' | 'POST'

interface RequestOptions {
  method?: Method
  body?: unknown
  signal?: AbortSignal
}

interface ErrorEnvelope {
  error?: { code?: unknown; message?: unknown }
}

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number | null,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function safeError(response: Response, value: unknown): ApiError {
  const envelope = value as ErrorEnvelope | null
  const code = typeof envelope?.error?.code === 'string' ? envelope.error.code : 'request_failed'
  const backendMessage =
    typeof envelope?.error?.message === 'string' ? envelope.error.message : undefined
  const safeMessages: Record<string, string> = {
    email_registered: 'An account with this email already exists.',
    invalid_credentials: 'Email or password is incorrect.',
    validation_error: 'Please check the information you entered.',
    csrf_rejected: 'This request could not be verified. Please refresh and try again.',
  }

  return new ApiError(
    code,
    response.status,
    safeMessages[code] ??
      (response.status < 500 ? backendMessage : undefined) ??
      'Something went wrong. Please try again.',
  )
}

async function parseJson(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return undefined
  try {
    return await response.json()
  } catch {
    return undefined
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      credentials: 'include',
      headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(
      'network_error',
      null,
      'Unable to reach KeptIt. Check your connection and try again.',
    )
  }

  const data = await parseJson(response)
  if (!response.ok) throw safeError(response, data)
  return data as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => apiRequest<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'POST', body }),
}
