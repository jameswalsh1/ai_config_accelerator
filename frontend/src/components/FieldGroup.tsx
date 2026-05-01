import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import type { EditableField } from '@/types/wizard'

export type FieldGroupKey = 'overridden' | 'default' | 'locked' | 'suggested'

interface FieldGroupProps {
  title: string
  count: number
  isExpanded: boolean
  onToggle: () => void
  icon: 'indigo' | 'red' | 'amber' | 'gray'
  children: ReactNode
}

const ICON_COLORS = {
  indigo: 'bg-indigo-100 text-indigo-700',
  red: 'bg-red-100 text-red-700',
  amber: 'bg-amber-100 text-amber-700',
  gray: 'bg-gray-100 text-gray-700',
}

const BORDER_COLORS = {
  indigo: 'border-l-indigo-600',
  red: 'border-l-red-600',
  amber: 'border-l-amber-600',
  gray: 'border-l-gray-400',
}

export function FieldGroup({ title, count, isExpanded, onToggle, icon, children }: FieldGroupProps) {
  return (
    <div
      className={`rounded-lg border-l-4 overflow-hidden shadow transition-all ${
        BORDER_COLORS[icon]
      } ${isExpanded ? 'shadow-md border-gray-200' : 'shadow-sm border-gray-100 hover:shadow-md'}`}
    >
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between px-6 py-4 transition-colors ${
          isExpanded ? 'bg-gradient-to-r from-gray-50 to-white border-b border-gray-200' : 'hover:bg-gray-50 bg-white'
        }`}
      >
        <div className="flex items-center gap-4">
          <h3 className="font-semibold text-gray-900 text-lg">{title}</h3>
          <span
            className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
              ICON_COLORS[icon]
            }`}
          >
            {count}
          </span>
        </div>
        <ChevronDown
          className={`size-5 text-gray-500 transition-transform flex-shrink-0 ${
            isExpanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isExpanded && (
        <div className="px-6 py-4 space-y-4 bg-gradient-to-b from-white to-gray-50">
          {children}
        </div>
      )}
    </div>
  )
}

export function groupFieldsByStatus(
  fields: EditableField[]
): Record<FieldGroupKey, EditableField[]> {
  return fields.reduce(
    (acc, field) => {
      if (field.is_locked) {
        acc.locked.push(field)
      } else if (!field.is_default) {
        acc.overridden.push(field)
      } else if (field.editability === 'suggested') {
        acc.suggested.push(field)
      } else {
        acc.default.push(field)
      }
      return acc
    },
    {
      overridden: [] as EditableField[],
      default: [] as EditableField[],
      locked: [] as EditableField[],
      suggested: [] as EditableField[],
    }
  )
}
