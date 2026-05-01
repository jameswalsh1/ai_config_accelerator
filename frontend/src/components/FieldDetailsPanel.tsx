import React, { useState } from 'react'
import { ChevronDown, Lock, Unlock, Copy, ExternalLink } from 'lucide-react'
import type { EditableField } from '@/types/wizard'

interface FieldDetailsPanelProps {
  field: EditableField
  sourceLabel: string
  onLockToggle: (field: EditableField) => void
  onResetToBase: (field: EditableField) => void
  onEditMetadata: (fieldId: string) => void
  isUpdating: boolean
}

const SOURCE_COLORS: Record<string, string> = {
  base: 'bg-slate-100 text-slate-700',
  tool: 'bg-indigo-100 text-indigo-700',
  language: 'bg-green-100 text-green-700',
  override: 'bg-purple-100 text-purple-700',
  preset: 'bg-orange-100 text-orange-700',
}

const EDITABILITY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  free: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700' },
  locked: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700' },
  suggested: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' },
  defaulted: { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-700' },
}

export function FieldDetailsPanel({
  field,
  sourceLabel,
  onLockToggle,
  onResetToBase,
  onEditMetadata,
  isUpdating,
}: FieldDetailsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const sourceColor = SOURCE_COLORS[sourceLabel] || SOURCE_COLORS.base
  const editabilityColor = EDITABILITY_COLORS[field.editability]

  const handleCopyValue = () => {
    const value = field.current_value ?? field.default ?? ''
    const textToCopy = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    navigator.clipboard.writeText(textToCopy)
  }

  return (
    <div className="space-y-2">
      {/* Expandable Details Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors border border-gray-200"
        title="Show field details and metadata"
      >
        <span>Field Details</span>
        <ChevronDown
          className={`size-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Expanded Details Panel */}
      {isExpanded && (
        <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-gray-50 to-white p-4 shadow-sm space-y-4">
          {/* Source Information */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
              Source & Origin
            </h4>
            <div className="flex flex-wrap gap-2">
              <span
                className={`inline-block px-3 py-1 rounded-md text-xs font-medium ${sourceColor}`}
                title={`Field source: ${sourceLabel}`}
              >
                {sourceLabel}
              </span>
              <span
                className={`inline-block px-3 py-1 rounded-md text-xs font-medium border ${editabilityColor.border} ${editabilityColor.text} bg-white`}
                title={`Editability: ${field.editability}`}
              >
                {field.editability}
              </span>
            </div>
            {field.source_file && (
              <p className="text-xs text-gray-500 italic break-all">
                <span className="font-medium">File:</span> {field.source_file}
              </p>
            )}
          </div>

          {/* Lock Information — shows what wizard users will see */}
          {field.is_locked && (
            <div className="space-y-2 bg-amber-50 border border-amber-200 rounded-md p-3">
              <div className="flex items-center gap-2">
                <Lock className="size-4 text-amber-700" />
                <h4 className="text-xs font-semibold text-amber-900">Locked for wizard users</h4>
              </div>
              {field.lock_reason && (
                <p className="text-xs text-amber-800">{field.lock_reason}</p>
              )}
              {!field.lock_reason && (
                <p className="text-xs text-amber-700 italic">No reason specified — consider adding one so users understand why.</p>
              )}
            </div>
          )}

          {/* Default Value Information */}
          {field.default !== undefined && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Default Value
              </h4>
              <div className="bg-white border border-gray-200 rounded-md p-2.5">
                <code className="text-xs text-gray-700 break-all">
                  {typeof field.default === 'string'
                    ? field.default || '(empty)'
                    : JSON.stringify(field.default, null, 2)}
                </code>
              </div>
            </div>
          )}

          {/* Current Value Information */}
          {field.current_value !== undefined && field.current_value !== field.default && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Current Value
              </h4>
              <div className="bg-white border border-gray-200 rounded-md p-2.5">
                <code className="text-xs text-gray-700 break-all">
                  {typeof field.current_value === 'string'
                    ? field.current_value || '(empty)'
                    : JSON.stringify(field.current_value, null, 2)}
                </code>
              </div>
            </div>
          )}

          {/* Is Default Indicator */}
          {field.is_default && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-2.5">
              <p className="text-xs text-blue-800 font-medium">✓ Using default value</p>
            </div>
          )}

          {/* Tracking Information */}
          {field.current_value_source && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Value Source
              </h4>
              <p className="text-xs text-gray-700 bg-white border border-gray-200 rounded-md px-2.5 py-2">
                {field.current_value_source}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
            {/* Copy Value Button */}
            <button
              onClick={handleCopyValue}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors border border-blue-200"
              title="Copy field value to clipboard"
            >
              <Copy className="size-3" />
              Copy Value
            </button>

            {/* Edit Metadata Button — always shown for the SME, even if locked for users */}
            {field.override_source && (
              <button
                onClick={() => onEditMetadata(field.id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors border border-indigo-200"
                disabled={isUpdating}
                title="Edit field metadata"
              >
                <ExternalLink className="size-3" />
                Edit Metadata
              </button>
            )}

            {/* Lock/Unlock for wizard users — SMEs control whether end users can edit */}
            {field.override_source && (
              <button
                onClick={() => onLockToggle(field)}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors border ${
                  field.is_locked
                    ? 'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border-gray-300'
                }`}
                title={field.is_locked ? 'Allow wizard users to edit this field' : 'Prevent wizard users from editing this field'}
                disabled={isUpdating}
              >
                {field.is_locked ? (
                  <>
                    <Unlock className="size-3" />
                    Unlock for users
                  </>
                ) : (
                  <>
                    <Lock className="size-3" />
                    Lock for users
                  </>
                )}
              </button>
            )}

            {/* Reset to Base Button */}
            {field.override_source && !field.is_default && (
              <button
                onClick={() => onResetToBase(field)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors border border-amber-200"
                disabled={isUpdating}
                title="Reset to base/tool defaults"
              >
                <span>↺ Reset</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
