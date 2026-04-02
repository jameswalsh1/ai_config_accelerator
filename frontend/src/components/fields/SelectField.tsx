import type { WizardField } from '@/types/wizard'

interface SelectFieldProps {
  field: WizardField
  value: string
  error?: string
  onChange: (value: string) => void
}

export function SelectField({ field, value, error, onChange }: SelectFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={field.id} className="text-sm font-medium text-gray-700">
        {field.label}
        {field.required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {field.description && (
        <p className="text-xs text-gray-500">{field.description}</p>
      )}
      <div className="flex flex-col gap-2">
        {(field.options ?? []).map(opt => (
          <label
            key={opt.value}
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition hover:bg-indigo-50 ${
              value === opt.value
                ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500'
                : error
                ? 'border-red-300'
                : 'border-gray-200'
            }`}
          >
            <input
              type="radio"
              name={field.id}
              value={opt.value}
              checked={value === opt.value}
              onChange={() => onChange(opt.value)}
              className="mt-0.5 accent-indigo-600"
            />
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium text-gray-800">{opt.label}</span>
              {opt.description && (
                <span className="text-xs text-gray-500">{opt.description}</span>
              )}
            </div>
          </label>
        ))}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
