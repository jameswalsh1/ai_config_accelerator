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

  if (field.type === 'repeatable_group') {
    const entries = value as Record<string, unknown>[] | undefined
    if (!entries || entries.length === 0) return `${field.label} requires at least one entry`
    const singularLabel = (field.validation?.singular_label as string | undefined) ??
      (field.label.endsWith('s') ? field.label.slice(0, -1) : field.label)

    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i]
      for (const nestedField of field.fields ?? []) {
        // If the nested field is not required, skip. If it's marked render:false,
        // only validate it when the user explicitly included it via the companion include flag.
        if (!nestedField.required) continue
        if (nestedField.render === false) {
          const included = Boolean(entry[`${nestedField.id}__include`])
          if (!included) continue
        }
        const nestedValue = entry[nestedField.id] ?? nestedField.default
        const isEmpty =
          nestedValue === undefined ||
          nestedValue === null ||
          nestedValue === '' ||
          (Array.isArray(nestedValue) && nestedValue.length === 0)
        if (isEmpty) {
          return `${nestedField.label} is required for ${singularLabel} ${i + 1}`
        }
      }
    }
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
  activeTags: string[]
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

  const activeTags = useMemo(() => {
    const tags = new Set<string>()
    for (const step of config.steps) {
      for (const field of step.fields) {
        if (!field.tag_source) continue
        const value = answers[step.id]?.[field.id] ?? field.default
        if (Array.isArray(value)) {
          value.forEach(item => {
            if (typeof item === 'string' && item.trim()) {
              tags.add(item.trim())
            }
          })
        } else if (typeof value === 'string' && value.trim()) {
          tags.add(value.trim())
        }
      }
    }
    return Array.from(tags)
  }, [config.steps, answers])

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
    activeTags,
    fieldError,
    isFirstScreen: currentScreenIndex === 0,
    isLastScreen: currentScreenIndex === screens.length - 1,
    setFieldValue,
    nextScreen,
    prevScreen,
    reset,
  }
}
