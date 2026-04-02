import { useCallback, useMemo, useState } from 'react'
import type { AgentEntry, WizardAnswers, WizardConfig, WizardField, WizardStep } from '@/types/wizard'

export interface Screen {
  stepIndex: number
  fieldIndex: number
  step: WizardStep
  field: WizardField
  /** true when this is the first field belonging to the step */
  isFirstFieldOfStep: boolean
}

function buildScreens(config: WizardConfig): Screen[] {
  const screens: Screen[] = []
  for (let si = 0; si < config.steps.length; si++) {
    const step = config.steps[si]
    for (let fi = 0; fi < step.fields.length; fi++) {
      screens.push({ stepIndex: si, fieldIndex: fi, step, field: step.fields[fi], isFirstFieldOfStep: fi === 0 })
    }
  }
  return screens
}

function validateField(field: WizardField, value: unknown): string | null {
  if (!field.required) return null

  if (field.type === 'agent_list') {
    const agents = value as AgentEntry[] | undefined
    if (!agents || agents.length === 0) return `${field.label} requires at least one agent`
    const hasUnnamed = agents.some(a => !a.name?.trim())
    if (hasUnnamed) return 'All agents must have a name before continuing'
    return null
  }

  const isEmpty =
    value === undefined ||
    value === null ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  return isEmpty ? `${field.label} is required` : null
}

export interface UseWizardReturn {
  screens: Screen[]
  currentScreenIndex: number
  currentScreen: Screen
  answers: WizardAnswers
  fieldError: string | null
  isFirstScreen: boolean
  isLastScreen: boolean
  setFieldValue: (stepId: string, fieldId: string, value: unknown) => void
  nextScreen: () => boolean
  prevScreen: () => void
  reset: () => void
}

export function useWizard(config: WizardConfig): UseWizardReturn {
  const screens = useMemo(() => buildScreens(config), [config])
  const [currentScreenIndex, setCurrentScreenIndex] = useState(0)
  const [answers, setAnswers] = useState<WizardAnswers>({})
  const [fieldError, setFieldError] = useState<string | null>(null)

  const setFieldValue = useCallback((stepId: string, fieldId: string, value: unknown) => {
    setAnswers(prev => ({ ...prev, [stepId]: { ...prev[stepId], [fieldId]: value } }))
    setFieldError(null)
  }, [])

  const nextScreen = useCallback((): boolean => {
    const { step, field } = screens[currentScreenIndex]
    // Fall back to field.default so required fields with defaults pass without user interaction
    const value = answers[step.id]?.[field.id] ?? field.default
    const error = validateField(field, value)
    if (error) {
      setFieldError(error)
      return false
    }
    setFieldError(null)
    if (currentScreenIndex < screens.length - 1) {
      setCurrentScreenIndex(i => i + 1)
    }
    return true
  }, [screens, currentScreenIndex, answers])

  const prevScreen = useCallback(() => {
    setFieldError(null)
    setCurrentScreenIndex(i => Math.max(0, i - 1))
  }, [])

  const reset = useCallback(() => {
    setCurrentScreenIndex(0)
    setAnswers({})
    setFieldError(null)
  }, [])

  return {
    screens,
    currentScreenIndex,
    currentScreen: screens[currentScreenIndex],
    answers,
    fieldError,
    isFirstScreen: currentScreenIndex === 0,
    isLastScreen: currentScreenIndex === screens.length - 1,
    setFieldValue,
    nextScreen,
    prevScreen,
    reset,
  }
}
