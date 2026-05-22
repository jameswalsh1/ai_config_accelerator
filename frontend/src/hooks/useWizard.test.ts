import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWizard } from './useWizard'
import type { WizardConfig, WizardStep, WizardField } from '@/types/wizard'

function makeField(overrides: Partial<WizardField> = {}): WizardField {
  return {
    id: 'field1',
    type: 'text',
    label: 'Field 1',
    required: false,
    ...overrides,
  }
}

function makeStep(overrides: Partial<WizardStep> = {}): WizardStep {
  return {
    id: 'step1',
    title: 'Step 1',
    fields: [makeField()],
    output_file: 'out.md',
    ...overrides,
  }
}

function makeConfig(overrides: Partial<WizardConfig> = {}): WizardConfig {
  return {
    id: 'test',
    title: 'Test Config',
    description: 'Test',
    target: 'copilot',
    steps: [
      makeStep({ id: 'step1', title: 'Step 1', fields: [makeField({ id: 'f1', label: 'F1' })] }),
      makeStep({ id: 'step2', title: 'Step 2', fields: [makeField({ id: 'f2', label: 'F2' })] }),
    ],
    ...overrides,
  }
}

describe('useWizard', () => {
  describe('screen building', () => {
    it('builds screens from config steps', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      expect(result.current.screens).toHaveLength(2)
      expect(result.current.screens[0].step.id).toBe('step1')
      expect(result.current.screens[1].step.id).toBe('step2')
    })

    it('filters out hidden steps', () => {
      const config = makeConfig({
        steps: [
          makeStep({ id: 'visible', hidden: false }),
          makeStep({ id: 'hidden', hidden: true }),
          makeStep({ id: 'also_visible' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      expect(result.current.screens).toHaveLength(2)
      expect(result.current.screens.map(s => s.step.id)).toEqual(['visible', 'also_visible'])
    })
  })

  describe('navigation', () => {
    it('starts on first screen', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      expect(result.current.currentScreenIndex).toBe(0)
      expect(result.current.isFirstScreen).toBe(true)
      expect(result.current.isLastScreen).toBe(false)
    })

    it('navigates forward', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => {
        result.current.nextScreen()
      })
      expect(result.current.currentScreenIndex).toBe(1)
      expect(result.current.isLastScreen).toBe(true)
    })

    it('navigates backward', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => { result.current.nextScreen() })
      act(() => { result.current.prevScreen() })
      expect(result.current.currentScreenIndex).toBe(0)
    })

    it('does not go below 0', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => { result.current.prevScreen() })
      expect(result.current.currentScreenIndex).toBe(0)
    })
  })

  describe('field values', () => {
    it('sets and retrieves field values', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => {
        result.current.setFieldValue('step1', 'f1', 'hello')
      })
      expect(result.current.answers).toEqual({ step1: { f1: 'hello' } })
    })

    it('preserves values across steps', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => {
        result.current.setFieldValue('step1', 'f1', 'value1')
        result.current.setFieldValue('step2', 'f2', 'value2')
      })
      expect(result.current.answers.step1.f1).toBe('value1')
      expect(result.current.answers.step2.f2).toBe('value2')
    })

    it('re-bases untouched fields to new config defaults on rerender', () => {
      const initialConfig = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [
              makeField({ id: 'language', label: 'Language', type: 'select', default: 'typescript' }),
              makeField({ id: 'conventions', label: 'Conventions', default: 'TS defaults' }),
            ],
          }),
        ],
      })

      const pythonConfig = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [
              makeField({ id: 'language', label: 'Language', type: 'select', default: 'python' }),
              makeField({ id: 'conventions', label: 'Conventions', default: 'Python defaults' }),
            ],
          }),
        ],
      })

      const { result, rerender } = renderHook(
        ({ cfg }) => useWizard(cfg),
        { initialProps: { cfg: initialConfig } },
      )

      // User explicitly changes only the language field.
      act(() => {
        result.current.setFieldValue('step1', 'language', 'python')
      })

      // Simulate wizard language switch loading language-specific config.
      rerender({ cfg: pythonConfig })

      // Touched field is preserved.
      expect(result.current.answers.step1.language).toBe('python')
      // Untouched field follows the new config defaults.
      expect(result.current.answers.step1.conventions).toBe('Python defaults')
    })
  })

  describe('validation', () => {
    it('blocks navigation when required field is empty', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [makeField({ id: 'req', label: 'Required', required: true })],
          }),
          makeStep({ id: 'step2' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      let advanced: boolean
      act(() => {
        advanced = result.current.nextScreen()
      })
      expect(advanced!).toBe(false)
      expect(result.current.fieldError).toBe('Required is required')
      expect(result.current.currentScreenIndex).toBe(0)
    })

    it('allows navigation when required field has value', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [makeField({ id: 'req', label: 'Required', required: true })],
          }),
          makeStep({ id: 'step2' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      act(() => {
        result.current.setFieldValue('step1', 'req', 'filled')
      })
      let advanced: boolean
      act(() => {
        advanced = result.current.nextScreen()
      })
      expect(advanced!).toBe(true)
      expect(result.current.fieldError).toBeNull()
      expect(result.current.currentScreenIndex).toBe(1)
    })

    it('allows navigation for non-required empty fields', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [makeField({ id: 'opt', label: 'Optional', required: false })],
          }),
          makeStep({ id: 'step2' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      let advanced: boolean
      act(() => {
        advanced = result.current.nextScreen()
      })
      expect(advanced!).toBe(true)
    })

    it('validates required field with default value', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [makeField({ id: 'req', label: 'R', required: true, default: 'default_val' })],
          }),
          makeStep({ id: 'step2' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      let advanced: boolean
      act(() => {
        advanced = result.current.nextScreen()
      })
      // Should pass because field has a default value
      expect(advanced!).toBe(true)
    })

    it('validates empty array as empty for required fields', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [makeField({ id: 'arr', label: 'Array Field', required: true, type: 'multi_select' })],
          }),
          makeStep({ id: 'step2' }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      act(() => {
        result.current.setFieldValue('step1', 'arr', [])
      })
      let advanced: boolean
      act(() => {
        advanced = result.current.nextScreen()
      })
      expect(advanced!).toBe(false)
      expect(result.current.fieldError).toBe('Array Field is required')
    })
  })

  describe('reset', () => {
    it('resets to initial state', () => {
      const { result } = renderHook(() => useWizard(makeConfig()))
      act(() => {
        result.current.setFieldValue('step1', 'f1', 'val')
        result.current.nextScreen()
      })
      expect(result.current.currentScreenIndex).toBe(1)
      act(() => {
        result.current.reset()
      })
      expect(result.current.currentScreenIndex).toBe(0)
      expect(result.current.answers).toEqual({})
      expect(result.current.fieldError).toBeNull()
    })
  })

  describe('activeTags', () => {
    it('collects tags from tag_source fields', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [
              makeField({
                id: 'lang',
                label: 'Language',
                type: 'select',
                tag_source: true,
                default: 'python',
              }),
            ],
          }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      expect(result.current.activeTags).toContain('python')
    })

    it('collects tags from multi-select tag_source fields', () => {
      const config = makeConfig({
        steps: [
          makeStep({
            id: 'step1',
            fields: [
              makeField({
                id: 'langs',
                label: 'Languages',
                type: 'multi_select',
                tag_source: true,
              }),
            ],
          }),
        ],
      })
      const { result } = renderHook(() => useWizard(config))
      act(() => {
        result.current.setFieldValue('step1', 'langs', ['python', 'java'])
      })
      expect(result.current.activeTags).toContain('python')
      expect(result.current.activeTags).toContain('java')
    })
  })
})
