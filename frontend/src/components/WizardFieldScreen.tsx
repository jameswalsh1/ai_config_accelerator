import { InfoIcon, LightbulbIcon, LockIcon } from 'lucide-react'
import type { Screen } from '@/hooks/useWizard'
import type { AgentEntry, WizardAnswers } from '@/types/wizard'
import { PresetBar } from './PresetBar'
import { AgentListField } from './fields/AgentListField'
import { CheckboxField } from './fields/CheckboxField'
import { MultiSelectField } from './fields/MultiSelectField'
import { SelectField } from './fields/SelectField'
import { TextAreaField } from './fields/TextAreaField'
import { TextField } from './fields/TextField'

interface WizardFieldScreenProps {
  screen: Screen
  answers: WizardAnswers
  fieldError: string | null
  onFieldChange: (fieldId: string, value: unknown) => void
}

export function WizardFieldScreen({ screen, answers, fieldError, onFieldChange }: WizardFieldScreenProps) {
  const { step, field, isFirstFieldOfStep, stepIndex } = screen
  const stepAnswers = answers[step.id] ?? {}

  const getStr = (fallback = '') =>
    (stepAnswers[field.id] as string | undefined) ??
    (field.default as string | undefined) ??
    fallback
  const getBool = (fallback = false) =>
    (stepAnswers[field.id] as boolean | undefined) ??
    (field.default as boolean | undefined) ??
    fallback
  const getArr = (): string[] =>
    (stepAnswers[field.id] as string[] | undefined) ?? []
  const getAgents = (): AgentEntry[] =>
    (stepAnswers[field.id] as AgentEntry[] | undefined) ?? []

  const currentValue = (): unknown => {
    switch (field.type) {
      case 'multi_select': return getArr()
      case 'agent_list': return getAgents()
      case 'checkbox': return getBool()
      default: return getStr()
    }
  }

  const renderField = () => {
    const error = fieldError ?? undefined
    switch (field.type) {
      case 'text':
        return <TextField field={field} value={getStr()} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'textarea':
        return <TextAreaField field={field} value={getStr()} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'select':
        return <SelectField field={field} value={getStr((field.default as string | undefined) ?? '')} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'multi_select':
        return <MultiSelectField field={field} value={getArr()} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'checkbox':
        return <CheckboxField field={field} value={getBool((field.default as boolean | undefined) ?? false)} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'agent_list':
        return <AgentListField field={field} value={getAgents()} error={error} onChange={v => onFieldChange(field.id, v)} />
      default:
        return null
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Step banner — step title + hint, shown once at the start of each step */}
      {isFirstFieldOfStep && (
        <div className="flex flex-col gap-2 border-b border-gray-100 pb-4">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">
              Step {stepIndex + 1}
            </span>
            <h2 className="text-base font-semibold text-gray-800">{step.title}</h2>
          </div>
          {step.description && (
            <p className="text-sm text-gray-500">{step.description}</p>
          )}
          {step.hint && (
            <div className="flex gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
              <InfoIcon className="mt-0.5 size-4 shrink-0 text-indigo-500" />
              <p className="text-xs leading-relaxed text-indigo-700">{step.hint}</p>
            </div>
          )}
        </div>
      )}

      {/* Per-field verbose instruction */}
      {field.screen_hint && (
        <div className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <LightbulbIcon className="mt-0.5 size-4 shrink-0 text-amber-500" />
          <p className="text-xs leading-relaxed text-amber-800">{field.screen_hint}</p>
        </div>
      )}

      {/* Field input */}
      <div className="flex flex-col gap-3">
        {/* Locked best-practice content — read-only, always included in output */}
        {field.locked_value && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <LockIcon className="size-3 text-gray-400" />
              <span className="text-xs font-medium text-gray-500">Best-practice defaults (always included)</span>
            </div>
            <pre className="whitespace-pre-wrap rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-500 select-none">{field.locked_value}</pre>
          </div>
        )}

        {renderField()}

        {/* Quick-fill preset chips */}
        {field.presets && field.presets.length > 0 && (
          <PresetBar
            presets={field.presets}
            fieldType={field.type}
            currentValue={currentValue()}
            onChange={v => onFieldChange(field.id, v)}
          />
        )}
      </div>
    </div>
  )
}
