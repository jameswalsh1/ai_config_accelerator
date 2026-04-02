import { InfoIcon } from 'lucide-react'
import type { WizardAnswers, WizardStep as WizardStepType } from '@/types/wizard'
import { CheckboxField } from './fields/CheckboxField'
import { MultiSelectField } from './fields/MultiSelectField'
import { SelectField } from './fields/SelectField'
import { TextAreaField } from './fields/TextAreaField'
import { TextField } from './fields/TextField'

interface WizardStepProps {
  step: WizardStepType
  answers: WizardAnswers
  validationErrors: Record<string, string>
  onFieldChange: (fieldId: string, value: unknown) => void
}

export function WizardStep({ step, answers, validationErrors, onFieldChange }: WizardStepProps) {
  const stepAnswers = answers[step.id] ?? {}

  const getStringValue = (fieldId: string, defaultVal = '') =>
    (stepAnswers[fieldId] as string | undefined) ?? defaultVal

  const getBooleanValue = (fieldId: string, defaultVal = false) =>
    (stepAnswers[fieldId] as boolean | undefined) ?? defaultVal

  const getArrayValue = (fieldId: string): string[] =>
    (stepAnswers[fieldId] as string[] | undefined) ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold text-gray-900">{step.title}</h2>
        {step.description && (
          <p className="text-sm text-gray-500">{step.description}</p>
        )}
      </div>

      {step.hint && (
        <div className="flex gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
          <InfoIcon className="mt-0.5 size-4 shrink-0 text-indigo-500" />
          <p className="text-sm text-indigo-700">{step.hint}</p>
        </div>
      )}

      <div className="flex flex-col gap-5">
        {step.fields.map(field => {
          const error = validationErrors[field.id]

          switch (field.type) {
            case 'text':
              return (
                <TextField
                  key={field.id}
                  field={field}
                  value={getStringValue(field.id, (field.default as string | undefined) ?? '')}
                  error={error}
                  onChange={v => onFieldChange(field.id, v)}
                />
              )
            case 'textarea':
              return (
                <TextAreaField
                  key={field.id}
                  field={field}
                  value={getStringValue(field.id, (field.default as string | undefined) ?? '')}
                  error={error}
                  onChange={v => onFieldChange(field.id, v)}
                />
              )
            case 'select':
              return (
                <SelectField
                  key={field.id}
                  field={field}
                  value={getStringValue(field.id, (field.default as string | undefined) ?? '')}
                  error={error}
                  onChange={v => onFieldChange(field.id, v)}
                />
              )
            case 'multi_select':
              return (
                <MultiSelectField
                  key={field.id}
                  field={field}
                  value={getArrayValue(field.id)}
                  error={error}
                  onChange={v => onFieldChange(field.id, v)}
                />
              )
            case 'checkbox':
              return (
                <CheckboxField
                  key={field.id}
                  field={field}
                  value={getBooleanValue(field.id, (field.default as boolean | undefined) ?? false)}
                  error={error}
                  onChange={v => onFieldChange(field.id, v)}
                />
              )
            default:
              return null
          }
        })}
      </div>
    </div>
  )
}
