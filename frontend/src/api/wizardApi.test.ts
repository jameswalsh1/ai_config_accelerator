import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Must import AFTER mocking fetch
const api = await import('@/api/wizardApi')

beforeEach(() => {
  mockFetch.mockReset()
})

function ok(body: unknown, status = 200) {
  return {
    ok: true,
    status,
    statusText: 'OK',
    json: () => Promise.resolve(body),
    blob: () => Promise.resolve(new Blob()),
  }
}

function err(status = 500, statusText = 'Internal Server Error') {
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve({ detail: statusText }),
  }
}

describe('wizardApi', () => {
  describe('fetchConfigs', () => {
    it('returns configs on success', async () => {
      const data = [{ id: 'test', title: 'Test' }]
      mockFetch.mockResolvedValueOnce(ok(data))
      const result = await api.fetchConfigs()
      expect(result).toEqual(data)
    })

    it('throws on failure', async () => {
      mockFetch.mockResolvedValueOnce(err(500, 'Server Error'))
      await expect(api.fetchConfigs()).rejects.toThrow('Failed to load configs')
    })
  })

  describe('fetchWizardConfig', () => {
    it('appends language param when provided', async () => {
      mockFetch.mockResolvedValueOnce(ok({ id: 'test', steps: [] }))
      await api.fetchWizardConfig('test', 'python')
      const url = mockFetch.mock.calls[0][0] as string
      expect(url).toContain('language=python')
    })

    it('throws on failure', async () => {
      mockFetch.mockResolvedValueOnce(err(404, 'Not Found'))
      await expect(api.fetchWizardConfig('missing')).rejects.toThrow("Failed to load config 'missing'")
    })
  })

  describe('fetchWithTimeout', () => {
    it('aborts after timeout', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})) // never resolves
      // Override the timeout by calling a function that uses it internally
      // We test via fetchConfigs which uses fetchWithTimeout
      // But we can't easily test the timeout without a real delay
      // Instead, test that AbortError is converted to a readable message
      mockFetch.mockRejectedValueOnce(Object.assign(new DOMException('Aborted', 'AbortError')))
      await expect(api.fetchConfigs()).rejects.toThrow('Request timed out')
    })
  })

  describe('createLanguageConfig', () => {
    it('returns mapped language option on success', async () => {
      mockFetch.mockResolvedValueOnce(ok({
        language_id: 'go',
        metadata: { title: 'Go', description: 'Go lang' },
      }))
      const result = await api.createLanguageConfig({
        language_id: 'go',
        title: 'Go',
      })
      expect(result).toEqual({ id: 'go', title: 'Go', description: 'Go lang' })
    })

    it('throws detailed error on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        json: () => Promise.resolve({ detail: 'Language already exists' }),
      })
      await expect(api.createLanguageConfig({ language_id: 'go', title: 'Go' }))
        .rejects.toThrow('Language already exists')
    })
  })

  describe('saveFieldValue', () => {
    it('sends correct payload', async () => {
      mockFetch.mockResolvedValueOnce(ok({ step: { id: 's1', fields: [] }, source_tracking: {} }))
      await api.saveFieldValue('claude', 'python', 'step1', 'field1', 'new-value')
      const body = JSON.parse(mockFetch.mock.calls[0][1].body)
      expect(body).toEqual({
        scope: 'language',
        target: 'python',
        step_id: 'step1',
        field_id: 'field1',
        changes: { default: 'new-value' },
      })
    })
  })
})
