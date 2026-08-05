import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl } from './config'

describe('API base URL configuration', () => {
  it('keeps the local default only in development', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe('http://localhost:8000')
    expect(() => resolveApiBaseUrl(undefined, true)).toThrow('required')
  })

  it('normalizes trailing slashes', () => {
    expect(resolveApiBaseUrl('https://api.example.com///', true)).toBe('https://api.example.com')
  })

  it('requires a safe HTTPS production origin', () => {
    expect(() => resolveApiBaseUrl('http://api.example.com', true)).toThrow('HTTPS')
    expect(() => resolveApiBaseUrl('https://api.example.com/path', true)).toThrow()
  })
})
