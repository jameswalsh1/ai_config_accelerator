import { AlertCircle } from 'lucide-react'
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
  validationError?: string
  onBlurValidation?: (fieldId: string, value: string) => void
}

export function FieldValueInput({
  field,
  value,
  onChange,
  onSave,
  validationError,
  onBlurValidation,
}: FieldValueInputProps) {
  const fieldId = field.id
  const baseClasses =
    'w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:border-transparent text-base shadow-sm transition-shadow hover:shadow-md'
  const validClasses = `${baseClasses} border-gray-300 focus:ring-indigo-500`
  const errorClasses = `${baseClasses} border-red-400 focus:ring-red-400 bg-red-50`
  const commonClasses = validationError ? errorClasses : validClasses

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
        </div>
      )

    case 'number':
      return (
        <input
          type="number"
          value={(value as number) || ''}
          onChange={e => onChange(e.target.value ? Number(e.target.value) : '')}
          onBlur={e => onSave(e.target.value ? Number(e.target.value) : '')}
          placeholder={field.placeholder}
          className={commonClasses}
        />
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
