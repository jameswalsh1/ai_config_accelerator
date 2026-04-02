import type { WizardField } from '@/types/wizard'

interface CheckboxFieldProps {
  field: WizardField
  value: boolean
  error?: string
  onChange: (value: boolean) => void
}

export function CheckboxField({ field, value, error, onChange }: CheckboxFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition hover:bg-indigo-50 ${
          value
            ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
            : error
            ? 'border-red-300'
            : 'border-gray-200'
        }`}
      >
        <input
          id={field.id}
          type="checkbox"
          checked={value}
          onChange={e => onChange(e.target.checked)}
          className="mt-0.5 accent-indigo-600"
        />
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-gray-800">{field.label}</span>
          {field.description && (
            <span className="text-xs text-gray-500">{field.description}</span>
          )}
        </div>
      </label>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
