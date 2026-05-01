import { AlertCircle, Check, Loader2 } from 'lucide-react'
import { useState, useEffect } from 'react'
import { RepeatableGroupField } from './fields/RepeatableGroupField'

interface FieldValueInputProps {
  field: {
    id: string
    type: string
    placeholder?: string
    rows?: number
    options?: { value: string; label: string; description?: string }[]
    description?: string
    fields?: any[]
  }
  value: unknown
  onChange: (value: unknown) => void
  onSave: (value: unknown) => void
  isDirty?: boolean
  isSaving?: boolean
  saveError?: string
  validationError?: string
  onBlurValidation?: (fieldId: string, value: string) => void
}

export function FieldValueInput({
  field,
  value,
  onChange,
  onSave,
  isDirty = false,
  isSaving = false,
  saveError,
  validationError,
  onBlurValidation,
}: FieldValueInputProps) {
  const fieldId = field.id
  const [showSaved, setShowSaved] = useState(false)

  // Show "Saved" briefly when isSaving transitions from true → false (only on success)
  const [wasSaving, setWasSaving] = useState(false)
  useEffect(() => {
    if (isSaving) {
      setWasSaving(true)
    } else if (wasSaving) {
      setWasSaving(false)
      if (!saveError) {
        setShowSaved(true)
        const t = setTimeout(() => setShowSaved(false), 2000)
        return () => clearTimeout(t)
      }
    }
  }, [isSaving, saveError])

  const baseClasses =
    'w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-base shadow-sm transition-shadow hover:shadow-md'
  const validClasses = `${baseClasses} border-gray-300 focus:ring-indigo-500`
  const errorClasses = `${baseClasses} border-red-400 focus:ring-red-400 bg-red-50`
  const dirtyClasses = `${baseClasses} border-indigo-400 focus:ring-indigo-500 ring-1 ring-indigo-200`
  const commonClasses = validationError ? errorClasses : isDirty ? dirtyClasses : validClasses

  const saveButton = (isDirty || showSaved || isSaving || saveError) && (
    <div className="flex items-center gap-2 mt-2">
      {isDirty && !isSaving && (
        <button
          type="button"
          onClick={() => onSave(value)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 transition-colors"
        >
          Save
        </button>
      )}
      {isSaving && (
        <span className="inline-flex items-center gap-1.5 text-sm text-indigo-600">
          <Loader2 className="size-3.5 animate-spin" />
          Saving…
        </span>
      )}
      {showSaved && !isSaving && !isDirty && !saveError && (
        <span className="inline-flex items-center gap-1 text-sm text-green-600">
          <Check className="size-3.5" />
          Saved
        </span>
      )}
      {saveError && !isSaving && (
        <span className="inline-flex items-center gap-1.5 text-sm text-red-600">
          <AlertCircle className="size-3.5 shrink-0" />
          {saveError}
        </span>
      )}
    </div>
  )

  switch (field.type) {
    case 'text':
      return (
        <div>
          <input
            type="text"
            value={(value as string) || ''}
            onChange={e => onChange(e.target.value)}
            onBlur={e => {
              onBlurValidation?.(fieldId, e.target.value)
              onSave(e.target.value)
            }}
            placeholder={field.placeholder}
            className={commonClasses}
          />
          {validationError && (
            <p className="flex items-center gap-1.5 mt-1.5 text-sm text-red-600">
              <AlertCircle className="size-4 shrink-0" />
              {validationError}
            </p>
          )}
          {saveButton}
        </div>
      )

    case 'number':
      return (
        <div>
          <input
            type="number"
            value={(value as number) || ''}
            onChange={e => onChange(e.target.value ? Number(e.target.value) : '')}
            onBlur={e => onSave(e.target.value ? Number(e.target.value) : '')}
            placeholder={field.placeholder}
            className={commonClasses}
          />
          {saveButton}
        </div>
      )

    case 'textarea':
      return (
        <div>
          <textarea
            value={(value as string) || ''}
            onChange={e => onChange(e.target.value)}
            onBlur={e => {
              onBlurValidation?.(fieldId, e.target.value)
              onSave(e.target.value)
            }}
            placeholder={field.placeholder}
            rows={field.rows || 4}
            className={`${commonClasses} resize-vertical font-mono text-sm`}
          />
          {validationError && (
            <p className="flex items-center gap-1.5 mt-1.5 text-sm text-red-600">
              <AlertCircle className="size-4 shrink-0" />
              {validationError}
            </p>
          )}
          {saveButton}
        </div>
      )

    case 'select':
      return (
        <select
          value={(value as string) || ''}
          onChange={e => { onChange(e.target.value); onSave(e.target.value) }}
          className={commonClasses}
        >
          <option value="">-- Select --</option>
          {field.options?.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )

    case 'multi_select':
    case 'multiselect': {
      const selectedValues = Array.isArray(value) ? value : []
      return (
        <div className="space-y-3 bg-white border border-gray-300 rounded-lg p-4">
          {field.options?.map(opt => (
            <label key={opt.value} className="flex items-start gap-3 cursor-pointer hover:bg-gray-50 p-2 rounded transition-colors">
              <input
                type="checkbox"
                checked={selectedValues.includes(opt.value)}
                onChange={e => {
                  const newValues = e.target.checked
                    ? [...selectedValues, opt.value]
                    : selectedValues.filter((v: string) => v !== opt.value)
                  onChange(newValues)
                  onSave(newValues)
                }}
                className="mt-1 rounded border-gray-300 w-4 h-4"
              />
              <div className="flex-1">
                <div className="text-base font-medium text-gray-900">{opt.label}</div>
                {opt.description && (
                  <div className="text-sm text-gray-600 mt-1">{opt.description}</div>
                )}
              </div>
            </label>
          ))}
        </div>
      )
    }

    case 'checkbox':
    case 'boolean':
      return (
        <label className="flex items-center gap-3 cursor-pointer p-3 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors w-fit">
          <input
            type="checkbox"
            checked={(value as boolean) || false}
            onChange={e => { onChange(e.target.checked); onSave(e.target.checked) }}
            className="h-5 w-5 rounded border-gray-300 text-indigo-600"
          />
          <span className="text-base text-gray-900 font-medium">Enabled</span>
        </label>
      )

    case 'repeatable_group': {
      const groupValues = Array.isArray(value) ? value : []
      return (
        <RepeatableGroupField
          field={field as any}
          value={groupValues}
          onChange={v => { onChange(v); onSave(v) }}
        />
      )
    }

    default:
      return (
        <div className="text-base text-gray-500 italic bg-gray-50 px-4 py-3 rounded-lg">
          Unsupported field type: {field.type}
        </div>
      )
  }
}
