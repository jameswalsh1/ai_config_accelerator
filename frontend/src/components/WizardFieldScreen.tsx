import { InfoIcon, LightbulbIcon, LockIcon } from 'lucide-react'
import type { Screen } from '@/hooks/useWizard'
import type { AgentEntry, WizardAnswers, WizardField } from '@/types/wizard'
import { PresetBar } from './PresetBar'
import { AgentListField } from './fields/AgentListField'
import { CheckboxField } from './fields/CheckboxField'
import { MultiSelectField } from './fields/MultiSelectField'
import { RepeatableGroupField } from './fields/RepeatableGroupField'
import { SelectField } from './fields/SelectField'
import { TextAreaField } from './fields/TextAreaField'
import { TextField } from './fields/TextField'

interface WizardFieldScreenProps {
  screen: Screen
  answers: WizardAnswers
  activeTags: string[]
  targetTag: string
  fieldError: string | null
  onFieldChange: (fieldId: string, value: unknown) => void
}

function getFieldValue(stepAnswers: Record<string, unknown>, field: WizardField, fieldType: string): unknown {
  switch (fieldType) {
    case 'multi_select':
      return (stepAnswers[field.id] as string[] | undefined) ?? []
    case 'agent_list':
      return (stepAnswers[field.id] as AgentEntry[] | undefined) ?? []
    case 'repeatable_group':
      return (stepAnswers[field.id] as Record<string, unknown>[] | undefined) ?? []
    case 'checkbox':
      return (stepAnswers[field.id] as boolean | undefined) ?? (field.default as boolean | undefined) ?? false
    default:
      return (stepAnswers[field.id] as string | undefined) ?? (field.default as string | undefined) ?? ''
  }
}

function renderSingleField(
  field: WizardField,
  stepAnswers: Record<string, unknown>,
  onFieldChange: (fieldId: string, value: unknown) => void,
  activeTags: string[],
  targetTag: string,
  fieldError: string | null
) {
  const fieldValue = getFieldValue(stepAnswers, field, field.type)
  const error = fieldError ?? undefined
  const includeKey = (id: string) => `${id}__include`
  const isIncluded = (id: string) => Boolean(stepAnswers[includeKey(id)])

  const renderFieldInput = () => {
    switch (field.type) {
      case 'text':
        return <TextField field={field} value={fieldValue as string} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'textarea':
        return <TextAreaField field={field} value={fieldValue as string} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'select':
        return <SelectField field={field} value={fieldValue as string} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'multi_select':
        return <MultiSelectField field={field} value={fieldValue as string[]} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'repeatable_group':
        return <RepeatableGroupField field={field} value={fieldValue as Record<string, unknown>[]} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'checkbox':
        return <CheckboxField field={field} value={fieldValue as boolean} error={error} onChange={v => onFieldChange(field.id, v)} />
      case 'agent_list':
        return <AgentListField field={field} value={fieldValue as AgentEntry[]} error={error} onChange={v => onFieldChange(field.id, v)} />
      default:
        return null
    }
  }

  return (
    <div key={field.id} className="flex flex-col gap-3 border-b border-gray-100 pb-6 last:border-0">
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

        {/* If a field is marked render:false in the config, surface it but make inclusion explicit */}
        {field.render === false && (
          <div className="flex items-center gap-3">
            <input
              id={`${field.id}-include`}
              type="checkbox"
              checked={isIncluded(field.id)}
              onChange={e => onFieldChange(includeKey(field.id), e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label htmlFor={`${field.id}-include`} className="text-sm text-gray-600">Include this optional field in the generated output</label>
          </div>
        )}

        {renderFieldInput()}

        {/* Quick-fill preset chips */}
        {field.presets && field.presets.length > 0 && (
          <PresetBar
            presets={field.presets}
            fieldType={field.type}
            currentValue={fieldValue}
            activeTags={activeTags}
            targetTag={targetTag}
            onChange={v => onFieldChange(field.id, v)}
          />
        )}
      </div>
    </div>
  )
}

export function WizardFieldScreen({ screen, answers, activeTags, targetTag, fieldError, onFieldChange }: WizardFieldScreenProps) {
  const { step, fields, stepIndex } = screen
  const stepAnswers = answers[step.id] ?? {}

  return (
    <div className="flex flex-col gap-5">
      {/* Step banner — step title + hint, shown once at the start of step */}
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

      {/* All fields for this step */}
      <div className="flex flex-col gap-5">
        {fields.map(field => renderSingleField(field, stepAnswers, onFieldChange, activeTags, targetTag, fieldError))}
      </div>
    </div>
  )
}
