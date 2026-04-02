import type { WizardField } from '@/types/wizard'

interface TextAreaFieldProps {
  field: WizardField
  value: string
  error?: string
  onChange: (value: string) => void
}

export function TextAreaField({ field, value, error, onChange }: TextAreaFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={field.id} className="text-sm font-medium text-gray-700">
        {field.label}
        {field.required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {field.description && (
        <p className="text-xs text-gray-500">{field.description}</p>
      )}
      <textarea
        id={field.id}
        value={value}
        placeholder={field.placeholder ?? ''}
        rows={field.rows ?? 4}
        onChange={e => onChange(e.target.value)}
        className={`rounded-md border px-3 py-2 text-sm shadow-sm outline-none transition focus:ring-2 focus:ring-indigo-500 resize-y ${
          error ? 'border-red-400 bg-red-50' : 'border-gray-300 bg-white'
        }`}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
