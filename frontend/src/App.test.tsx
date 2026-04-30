// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import App from './App'

// Mock all API calls so nothing hits the network
vi.mock('@/api/wizardApi', () => ({
  fetchConfigs: vi.fn(),
  fetchWizardConfig: vi.fn(),
  fetchAvailableTools: vi.fn(),
  fetchAvailableLanguages: vi.fn(),
  fetchAvailableSteps: vi.fn(),
  fetchEditableConfig: vi.fn(),
  fetchAuditLog: vi.fn(),
  fetchCoverageMatrix: vi.fn(),
}))

import {
  fetchConfigs,
  fetchWizardConfig,
  fetchAvailableTools,
  fetchAvailableLanguages,
  fetchAvailableSteps,
  fetchEditableConfig,
  fetchAuditLog,
  fetchCoverageMatrix,
} from '@/api/wizardApi'

const mockFetchConfigs = fetchConfigs as ReturnType<typeof vi.fn>
const mockFetchWizardConfig = fetchWizardConfig as ReturnType<typeof vi.fn>
const mockFetchAvailableTools = fetchAvailableTools as ReturnType<typeof vi.fn>
const mockFetchAvailableLanguages = fetchAvailableLanguages as ReturnType<typeof vi.fn>
const mockFetchAvailableSteps = fetchAvailableSteps as ReturnType<typeof vi.fn>
const mockFetchEditableConfig = fetchEditableConfig as ReturnType<typeof vi.fn>
const mockFetchAuditLog = fetchAuditLog as ReturnType<typeof vi.fn>
const mockFetchCoverageMatrix = fetchCoverageMatrix as ReturnType<typeof vi.fn>

const sampleConfigs = [
  { id: 'claude-java', title: 'Claude Java', description: 'Java config', target: 'claude' },
  { id: 'copilot-react', title: 'Copilot React', description: 'React config', target: 'copilot' },
]

beforeEach(() => {
  vi.clearAllMocks()
  // Default: resolve with empty data to prevent unhandled rejections
  mockFetchConfigs.mockResolvedValue([])
  mockFetchAvailableTools.mockResolvedValue([])
  mockFetchAvailableLanguages.mockResolvedValue([])
  mockFetchAvailableSteps.mockResolvedValue([])
  mockFetchEditableConfig.mockResolvedValue({ step: { id: 's1', title: 'Step 1', fields: [] }, scope: 'language', target: 'java' })
  mockFetchAuditLog.mockResolvedValue({ entries: [], total: 0 })
  mockFetchCoverageMatrix.mockResolvedValue({ tools: [], languages: [], matrix: {} })
})

describe('App', () => {
  describe('smoke render – every mode mounts without crashing', () => {
    it('renders the default config-selection mode', async () => {
      mockFetchConfigs.mockResolvedValue(sampleConfigs)
      await act(async () => { render(<App />) })
      expect(screen.getByRole('heading', { name: 'AI Config Accelerator' })).toBeInTheDocument()
      expect(screen.getByRole('navigation', { name: /main/i })).toBeInTheDocument()
    })

    it('renders config-editor mode', async () => {
      mockFetchConfigs.mockResolvedValue([])
      await act(async () => { render(<App />) })

      // Navigate to Config Editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Config Editor' }))
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Config Editor' })).toHaveAttribute('aria-current', 'page')
      })
    })

    it('renders audit-log mode', async () => {
      mockFetchConfigs.mockResolvedValue([])
      await act(async () => { render(<App />) })

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Audit Log' }))
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Audit Log' })).toHaveAttribute('aria-current', 'page')
      })
    })

    it('renders coverage mode', async () => {
      mockFetchConfigs.mockResolvedValue([])
      await act(async () => { render(<App />) })

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Coverage' }))
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Coverage' })).toHaveAttribute('aria-current', 'page')
      })
    })
  })

  describe('navigation between modes', () => {
    it('can navigate to every mode and back without error', async () => {
      mockFetchConfigs.mockResolvedValue(sampleConfigs)
      await act(async () => { render(<App />) })

      const modes = ['Config Editor', 'Audit Log', 'Coverage', 'Config Wizard']
      for (const label of modes) {
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: label }))
        })
        expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-current', 'page')
      }

      // Navigate back to config selection
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Config Wizard' }))
      })
      expect(screen.getByRole('button', { name: 'Config Wizard' })).toHaveAttribute('aria-current', 'page')
    })

    it('switches between modes repeatedly without hooks error', async () => {
      mockFetchConfigs.mockResolvedValue([])
      await act(async () => { render(<App />) })

      // Rapidly switch modes — this catches "rendered more hooks" errors
      for (let i = 0; i < 3; i++) {
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: 'Config Editor' }))
        })
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: 'Config Wizard' }))
        })
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: 'Audit Log' }))
        })
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: 'Coverage' }))
        })
      }
      // If we get here without throwing, hooks ordering is correct
      expect(screen.getByRole('button', { name: 'Coverage' })).toHaveAttribute('aria-current', 'page')
    })
  })

  describe('config list', () => {
    it('shows configs after loading', async () => {
      mockFetchConfigs.mockResolvedValue(sampleConfigs)
      await act(async () => { render(<App />) })

      await waitFor(() => {
        expect(screen.getByText('Claude Java')).toBeInTheDocument()
        expect(screen.getByText('Copilot React')).toBeInTheDocument()
      })
    })

    it('shows empty state when no configs exist', async () => {
      mockFetchConfigs.mockResolvedValue([])
      await act(async () => { render(<App />) })

      await waitFor(() => {
        expect(screen.getByText(/no configurations found/i)).toBeInTheDocument()
      })
    })

    it('shows error when fetchConfigs fails', async () => {
      mockFetchConfigs.mockRejectedValue(new Error('Network error'))
      await act(async () => { render(<App />) })

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
      })
    })
  })

  describe('wizard mode', () => {
    it('enters wizard mode when a config is selected', async () => {
      mockFetchConfigs.mockResolvedValue(sampleConfigs)
      mockFetchWizardConfig.mockResolvedValue({
        id: 'claude-java',
        title: 'Claude Java',
        description: 'Java config',
        target: 'claude',
        steps: [{ id: 'step1', title: 'Step 1', fields: [] }],
      })

      await act(async () => { render(<App />) })

      await waitFor(() => {
        expect(screen.getByText('Claude Java')).toBeInTheDocument()
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Claude Java').closest('button')!)
      })

      // Should have called fetchWizardConfig
      expect(mockFetchWizardConfig).toHaveBeenCalledWith('claude-java')
    })
  })
})
