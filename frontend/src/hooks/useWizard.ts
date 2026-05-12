import { useCallback, useMemo, useState } from 'react'
import type { AgentEntry, VisibilityRule, WizardAnswers, WizardConfig, WizardField, WizardFlowStep, WizardStep } from '@/types/wizard'

export interface Screen {
  stepIndex: number
  step: WizardStep
  fields: WizardField[]
}

// ---------------------------------------------------------------------------
// Client-side visibility rule evaluation
// ---------------------------------------------------------------------------

function resolveFieldValue(
  dependsOnFieldPath: string,
  answers: WizardAnswers,
  config: WizardConfig,
): unknown {
  const parts = dependsOnFieldPath.split('.', 2)
  if (parts.length !== 2) return undefined
  const [stepKey, fieldKey] = parts
  const explicit = answers[stepKey]?.[fieldKey]
  if (explicit !== undefined) return explicit
  // Fall back to field default
  const step = config.steps.find(s => s.id === stepKey)
  if (!step) return undefined
  const field = step.fields.find(f => f.id === fieldKey)
  return field?.default
}

function evaluateCondition(operator: string, fieldValue: unknown, ruleValue: unknown): boolean {
  switch (operator) {
    case 'equals': return fieldValue === ruleValue
    case 'not_equals': return fieldValue !== ruleValue
    case 'in': return Array.isArray(ruleValue) ? ruleValue.includes(fieldValue) : false
    case 'not_in': return Array.isArray(ruleValue) ? !ruleValue.includes(fieldValue) : true
    case 'is_empty':
      return fieldValue === null || fieldValue === undefined || fieldValue === '' ||
        (Array.isArray(fieldValue) && fieldValue.length === 0)
    case 'is_not_empty':
      return !(fieldValue === null || fieldValue === undefined || fieldValue === '' ||
        (Array.isArray(fieldValue) && fieldValue.length === 0))
    default: return false
  }
}

export function evaluateVisibilityRules(
  rules: VisibilityRule[],
  answers: WizardAnswers,
  config: WizardConfig,
): { steps: Record<string, boolean>; fields: Record<string, boolean> } {
  const steps: Record<string, boolean> = {}
  const fields: Record<string, boolean> = {}

  // Sort by priority (lower first, higher wins by overwriting)
  const sorted = [...rules].sort((a, b) => a.priority - b.priority)

  for (const rule of sorted) {
    const fieldValue = resolveFieldValue(rule.depends_on_field_path, answers, config)
    const conditionMet = evaluateCondition(rule.operator, fieldValue, rule.value)
    const visible = rule.action === 'show' ? conditionMet : !conditionMet

    if (rule.target_type === 'step') {
      steps[rule.target_step_key] = visible
    } else if (rule.target_field_path) {
      fields[rule.target_field_path] = visible
    }
  }

  return { steps, fields }
}

// ---------------------------------------------------------------------------
// Screen building with visibility + flow support
// ---------------------------------------------------------------------------

function buildScreens(
  config: WizardConfig,
  visibilitySteps?: Record<string, boolean>,
  flowSteps?: WizardFlowStep[],
): Screen[] {
  const screens: Screen[] = []

  // Determine step order — use flow if provided, otherwise config order
  let orderedSteps: WizardStep[]
  if (flowSteps && flowSteps.length > 0) {
    const stepsByKey = new Map(config.steps.map(s => [s.id, s]))
    orderedSteps = []
    for (const fs of flowSteps) {
      if (!fs.is_enabled) continue
      const step = stepsByKey.get(fs.step_key)
      if (!step) continue
      // Apply custom title/description from flow
      const customized = { ...step }
      if (fs.custom_title) customized.title = fs.custom_title
      if (fs.custom_description) customized.description = fs.custom_description
      orderedSteps.push(customized)
    }
  } else {
    orderedSteps = config.steps
  }

  for (let si = 0; si < orderedSteps.length; si++) {
    const step = orderedSteps[si]
    // Static hidden flag
    if (step.hidden) continue
    // Dynamic visibility rule
    if (visibilitySteps && step.id in visibilitySteps && !visibilitySteps[step.id]) continue

    screens.push({ stepIndex: si, step, fields: step.fields })
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
  visibleFields: Record<string, boolean>
  setFieldValue: (stepId: string, fieldId: string, value: unknown) => void
  nextScreen: () => boolean
  prevScreen: () => void
  reset: () => void
}

export interface UseWizardOptions {
  visibilityRules?: VisibilityRule[]
  flowSteps?: WizardFlowStep[]
}

export function useWizard(config: WizardConfig, options?: UseWizardOptions): UseWizardReturn {
  const [currentScreenIndex, setCurrentScreenIndex] = useState(0)
  const [answers, setAnswers] = useState<WizardAnswers>({})
  const [fieldError, setFieldError] = useState<string | null>(null)

  const rules = options?.visibilityRules ?? []
  const flowSteps = options?.flowSteps

  // Evaluate visibility rules reactively based on answers
  const visibility = useMemo(() => {
    if (rules.length === 0) return { steps: {} as Record<string, boolean>, fields: {} as Record<string, boolean> }
    return evaluateVisibilityRules(rules, answers, config)
  }, [rules, answers, config])

  const screens = useMemo(
    () => buildScreens(config, visibility.steps, flowSteps),
    [config, visibility.steps, flowSteps]
  )

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
    const { step, fields } = screens[currentScreenIndex]
    
    // Validate all fields on the current step
    for (const field of fields) {
      const value = answers[step.id]?.[field.id] ?? field.default
      const error = validateField(field, value)
      if (error) {
        setFieldError(error)
        return false
      }
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

  // Clamp index when screens shrink due to visibility changes
  const clampedIndex = Math.min(currentScreenIndex, Math.max(0, screens.length - 1))

  return {
    screens,
    currentScreenIndex: clampedIndex,
    currentScreen: screens[clampedIndex],
    answers,
    activeTags,
    fieldError,
    isFirstScreen: clampedIndex === 0,
    isLastScreen: clampedIndex === screens.length - 1,
    visibleFields: visibility.fields,
    setFieldValue,
    nextScreen,
    prevScreen,
    reset,
  }
}
