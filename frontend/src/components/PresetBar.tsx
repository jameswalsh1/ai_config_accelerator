import { SparklesIcon } from 'lucide-react'
import type { FieldType, Preset } from '@/types/wizard'

interface PresetBarProps {
  presets: Preset[]
  fieldType: FieldType
  currentValue: unknown
  onChange: (newValue: unknown) => void
}

function deepMerge(
  target: Record<string, unknown>,
  source: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    const sv = source[key]
    const tv = result[key]
    if (
      sv !== null && typeof sv === 'object' && !Array.isArray(sv) &&
      tv !== null && typeof tv === 'object' && !Array.isArray(tv)
    ) {
      result[key] = deepMerge(tv as Record<string, unknown>, sv as Record<string, unknown>)
    } else {
      result[key] = sv
    }
  }
  return result
}

export function PresetBar({ presets, fieldType, currentValue, onChange }: PresetBarProps) {
  const applyPreset = (preset: Preset) => {
    const mode = preset.mode ?? 'append'

    switch (mode) {
      case 'replace':
        onChange(preset.value)
        break

      case 'merge_json': {
        try {
          const existing = JSON.parse(String(currentValue || '{}')) as Record<string, unknown>
          const fragment = preset.value as Record<string, unknown>
          onChange(JSON.stringify(deepMerge(existing, fragment), null, 2))
        } catch {
          onChange(preset.value)
        }
        break
      }

      case 'append':
      default: {
        if (fieldType === 'multi_select' || fieldType === 'agent_list') {
          const current = (currentValue as unknown[] | undefined) ?? []
          const toAdd = Array.isArray(preset.value) ? preset.value : [preset.value]
          onChange([...current, ...toAdd])
        } else {
          const current = String(currentValue ?? '')
          onChange(current ? `${current}\n${String(preset.value)}` : String(preset.value))
        }
        break
      }
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t border-dashed border-gray-200 pt-3">
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <SparklesIcon className="size-3" />
        <span>Quick fill</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => applyPreset(preset)}
            title={preset.description}
            className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 transition hover:border-indigo-400 hover:bg-indigo-100"
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  )
}
