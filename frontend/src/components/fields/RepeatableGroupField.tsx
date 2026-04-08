import { PlusIcon, Trash2Icon } from 'lucide-react'
import { PresetBar } from '../PresetBar'
import { CheckboxField } from './CheckboxField'
import { MultiSelectField } from './MultiSelectField'
import { SelectField } from './SelectField'
import { TextAreaField } from './TextAreaField'
import { TextField } from './TextField'
import type { WizardField } from '@/types/wizard'

interface RepeatableGroupFieldProps {
  field: WizardField
  value: Record<string, unknown>[]
  error?: string
  onChange: (value: Record<string, unknown>[]) => void
}

function makeDefaultEntry(field: WizardField): Record<string, unknown> {
  const entry: Record<string, unknown> = {}
  if (!field.fields) return entry

  for (const nested of field.fields) {
    if (nested.default !== undefined) {
      entry[nested.id] = nested.default
    } else if (nested.type === 'checkbox') {
      entry[nested.id] = false
    } else if (nested.type === 'multi_select') {
      entry[nested.id] = []
    } else {
      entry[nested.id] = ''
    }
    // If the nested field is marked render:false, add an explicit include flag defaulting to false
    if (nested.render === false) {
      entry[`${nested.id}__include`] = false
    }
  }

  return entry
}

function renderNestedField(
  nestedField: WizardField,
  entry: Record<string, unknown>,
  onUpdate: (patch: Partial<Record<string, unknown>>) => void,
) {
  const value = entry[nestedField.id] ?? nestedField.default

  const commonProps = {
    field: nestedField,
    error: undefined as string | undefined,
  }

  switch (nestedField.type) {
    case 'text':
      return (
        <div key={nestedField.id}>
          {nestedField.render === false && (
            <div className="flex items-center gap-3 mb-2">
              <input
                id={`${nestedField.id}-include`}
                type="checkbox"
                checked={Boolean(entry[`${nestedField.id}__include`])}
                onChange={e => onUpdate({ [`${nestedField.id}__include`]: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor={`${nestedField.id}-include`} className="text-xs text-gray-600">Include this optional field</label>
            </div>
          )}
          <TextField
            {...commonProps}
            value={String(value ?? '')}
            onChange={v => onUpdate({ [nestedField.id]: v })}
          />
        </div>
      )
    case 'textarea':
      return (
        <div key={nestedField.id}>
          {nestedField.render === false && (
            <div className="flex items-center gap-3 mb-2">
              <input
                id={`${nestedField.id}-include`}
                type="checkbox"
                checked={Boolean(entry[`${nestedField.id}__include`])}
                onChange={e => onUpdate({ [`${nestedField.id}__include`]: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor={`${nestedField.id}-include`} className="text-xs text-gray-600">Include this optional field</label>
            </div>
          )}
          <TextAreaField
            {...commonProps}
            value={String(value ?? '')}
            onChange={v => onUpdate({ [nestedField.id]: v })}
          />
        </div>
      )
    case 'select':
      return (
        <div key={nestedField.id}>
          {nestedField.render === false && (
            <div className="flex items-center gap-3 mb-2">
              <input
                id={`${nestedField.id}-include`}
                type="checkbox"
                checked={Boolean(entry[`${nestedField.id}__include`])}
                onChange={e => onUpdate({ [`${nestedField.id}__include`]: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor={`${nestedField.id}-include`} className="text-xs text-gray-600">Include this optional field</label>
            </div>
          )}
          <SelectField
            {...commonProps}
            value={String(value ?? '')}
            onChange={v => onUpdate({ [nestedField.id]: v })}
          />
        </div>
      )
    case 'multi_select':
      return (
        <div key={nestedField.id}>
          {nestedField.render === false && (
            <div className="flex items-center gap-3 mb-2">
              <input
                id={`${nestedField.id}-include`}
                type="checkbox"
                checked={Boolean(entry[`${nestedField.id}__include`])}
                onChange={e => onUpdate({ [`${nestedField.id}__include`]: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor={`${nestedField.id}-include`} className="text-xs text-gray-600">Include this optional field</label>
            </div>
          )}
          <MultiSelectField
            {...commonProps}
            value={(Array.isArray(value) ? value : []) as string[]}
            onChange={v => onUpdate({ [nestedField.id]: v })}
          />
        </div>
      )
    case 'checkbox':
      return (
        <div key={nestedField.id}>
          {nestedField.render === false && (
            <div className="flex items-center gap-3 mb-2">
              <input
                id={`${nestedField.id}-include`}
                type="checkbox"
                checked={Boolean(entry[`${nestedField.id}__include`])}
                onChange={e => onUpdate({ [`${nestedField.id}__include`]: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor={`${nestedField.id}-include`} className="text-xs text-gray-600">Include this optional field</label>
            </div>
          )}
          <CheckboxField
            {...commonProps}
            value={Boolean(value)}
            onChange={v => onUpdate({ [nestedField.id]: v })}
          />
        </div>
      )
    default:
      return null
  }
}

export function RepeatableGroupField({ field, value, error, onChange }: RepeatableGroupFieldProps) {
  const entries = value ?? []

  const singularLabel = (field.validation?.singular_label as string | undefined) ??
    // naive singularization: drop trailing 's' if present
    (field.label.endsWith('s') ? field.label.slice(0, -1) : field.label)

  const addEntry = () => {
    onChange([...entries, makeDefaultEntry(field)])
  }

  const updateEntry = (idx: number, patch: Partial<Record<string, unknown>>) => {
    const next = [...entries]
    next[idx] = { ...next[idx], ...patch }
    onChange(next)
  }

  const removeEntry = (idx: number) => {
    onChange(entries.filter((_, i) => i !== idx))
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <label className="text-sm font-medium text-gray-700">
          {field.label}
          {field.required && <span className="ml-1 text-red-500">*</span>}
        </label>
        {field.description && (
          <p className="text-xs text-gray-500">{field.description}</p>
        )}
      </div>

      {entries.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
          No entries yet. Click "Add {singularLabel}" to create the first {singularLabel.toLowerCase()}.
        </div>
      )}

      <div className="flex flex-col gap-4">
        {entries.map((entry, idx) => (
          <div key={idx} className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-4 py-3 bg-gray-50 border-b border-gray-100">
              <div>
                <div className="text-sm font-semibold text-gray-800">{singularLabel} {idx + 1}</div>
                <p className="text-xs text-gray-500">Configure the {singularLabel.toLowerCase()} metadata and content for this file.</p>
              </div>
              <button
                type="button"
                onClick={() => removeEntry(idx)}
                className="rounded-md border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-100"
              >
                Remove
              </button>
            </div>
            <div className="flex flex-col gap-4 p-4">
              {(field.fields ?? []).map(nested => (
                <div key={nested.id}>
                  {renderNestedField(nested, entry, patch => updateEntry(idx, patch))}
                  {nested.presets && nested.presets.length > 0 && (
                    <PresetBar
                      presets={nested.presets}
                      fieldType={nested.type}
                      currentValue={entry[nested.id]}
                      activeTags={[]}
                      targetTag=""
                      onChange={newValue => updateEntry(idx, { [nested.id]: newValue })}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addEntry}
        className="inline-flex items-center gap-2 self-start rounded-md border border-dashed border-indigo-300 px-4 py-2 text-sm font-medium text-indigo-600 transition hover:border-indigo-500 hover:bg-indigo-50"
      >
        <PlusIcon className="size-4" />
        {`Add ${singularLabel}`}
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
