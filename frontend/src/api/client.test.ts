import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, UNAUTHORIZED_EVENT } from './client'

afterEach(() => vi.restoreAllMocks())

describe('api client', () => {
  it('includes browser credentials on GET and POST requests', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await api.get('/one')
    await api.post('/two', { value: 1 })
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include', method: 'GET' })
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: 'include', method: 'POST' })
  })

  it('turns network and unsafe server failures into typed safe errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('secret network detail'))
    await expect(api.get('/one')).rejects.toMatchObject({
      code: 'network_error',
      status: null,
    })
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: 'database_failure', message: 'SQL traceback' } }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    await expect(api.get('/two')).rejects.toMatchObject({
      message: 'Something went wrong. Please try again.',
    })
  })

  it('announces a 401 so authenticated UI state can be cleared', async () => {
    const unauthorized = vi.fn()
    window.addEventListener(UNAUTHORIZED_EVENT, unauthorized)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'unauthenticated' } }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(api.get('/protected')).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).toHaveBeenCalledOnce()
    window.removeEventListener(UNAUTHORIZED_EVENT, unauthorized)
  })
})
