import { afterEach, describe, expect, it, vi } from 'vitest'

import { getHealth } from './health'

describe('getHealth', () => {
  afterEach(() => vi.restoreAllMocks())

  it('returns the backend health response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ service: 'KeptIt API', status: 'ok' }), { status: 200 }),
    )

    await expect(getHealth()).resolves.toEqual({ service: 'KeptIt API', status: 'ok' })
  })

  it('throws when the backend is unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 503 }))

    await expect(getHealth()).rejects.toThrow('Health request failed with status 503')
  })
})
