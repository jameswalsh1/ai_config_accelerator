import React, { useState } from 'react'
import { Lock, Unlock, AlertCircle, CheckCircle2, ChevronDown, Edit3 } from 'lucide-react'
import type { EditableField, EditableStep, Editability } from '@/types/wizard'
import { updateFieldMetadata } from '@/api/wizardApi'

interface StepFieldEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown) => void
  onToggleLock?: (fieldId: string, locked: boolean) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
}

interface StepFieldEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown) => void
  onToggleLock?: (fieldId: string, locked: boolean) => void
}

type FieldGroup = 'overridden' | 'default' | 'locked' | 'suggested'

const EDITABILITY_COLORS: Record<Editability, { bg: string; border: string; text: string }> = {
  free: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700' },
  locked: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700' },
  suggested: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' },
  defaulted: { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-700' },
}

const SOURCE_COLORS: Record<string, string> = {
  base: 'bg-slate-100 text-slate-700',
  tool: 'bg-indigo-100 text-indigo-700',
  language: 'bg-green-100 text-green-700',
  override: 'bg-purple-100 text-purple-700',
}

export function StepFieldEditor({
  editableStep,
  onFieldChange,
  onToggleLock,
  onMetadataUpdate,
}: StepFieldEditorProps) {
  const { step, source_tracking } = editableStep
  const [expandedGroups, setExpandedGroups] = useState<Record<FieldGroup, boolean>>({ // eslint-disable-line @typescript-eslint/no-unused-vars
    overridden: true,
    default: true,
    locked: true,
    suggested: true,
  })
  const [editingMetadata, setEditingMetadata] = useState<string | null>(null)
  const [metadataChanges, setMetadataChanges] = useState<Record<string, unknown>>({})
  const [updating, setUpdating] = useState(false)

  // Group fields by status for clear organization
  const groupedFields = groupFieldsByStatus(step.fields)

  const handleMetadataUpdate = async (fieldId: string, changes: Record<string, unknown>) => {
    const field = step.fields.find(f => f.id === fieldId)
    if (!field || !field.override_source) return

    // Parse override_source like "language:python" or "tool:claude"
    const [scope, target] = field.override_source.split(':', 2)
    if (!scope || !target) return

    try {
      setUpdating(true)
      const updatedStep = await updateFieldMetadata(scope, target, step.id, fieldId, changes)
      onMetadataUpdate?.(updatedStep)
    } catch (error) {
      console.error('Failed to update metadata:', error)
      // Could add error state here
    } finally {
      setUpdating(false)
      setEditingMetadata(null)
      setMetadataChanges({})
    }
  }

  const startEditingMetadata = (fieldId: string) => {
    const field = step.fields.find(f => f.id === fieldId)
    if (!field) return

    setEditingMetadata(fieldId)
    setMetadataChanges({
      default: field.default,
      editability: field.editability,
      hidden: field.render === false, // Assuming render=false means hidden
    })
  }

  const cancelEditingMetadata = () => {
    setEditingMetadata(null)
    setMetadataChanges({})
  }

  const getSourceLabel = (field: EditableField): string => {
    if (field.override_source) return field.override_source
    if (field.source_file?.includes('tool')) return 'tool'
    if (field.source_file?.includes('language')) return 'language'
    return 'base'
  }

  const renderField = (field: EditableField) => {
    const sourceLabel = getSourceLabel(field)
    const sourceColor = SOURCE_COLORS[sourceLabel] || SOURCE_COLORS.base
    const canEdit = field.editability === 'free' && !field.is_locked
    const displayValue = field.current_value ?? field.default ?? ''
    const isEditingMetadata = editingMetadata === field.id

    return (
      <div
        key={field.id}
        className={`flex flex-col gap-3 p-4 rounded-lg border-l-4 transition-colors ${
          EDITABILITY_COLORS[field.editability].bg
        } border-b ${EDITABILITY_COLORS[field.editability].border}`}
      >
        {/* Field Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-gray-900">{field.label}</h4>
              {field.required && <span className="text-red-500 text-sm">*</span>}
              {field.is_locked && (
                <span title="This field is locked">
                  <Lock className="size-4 text-red-500" />
                </span>
              )}
              {field.is_default && (
                <span title="Using default value">
                  <CheckCircle2 className="size-4 text-gray-400" />
                </span>
              )}
            </div>

            {field.description && (
              <p className="text-xs text-gray-600 mb-2">{field.description}</p>
            )}

            {/* Metadata Row */}
            <div className="flex flex-wrap items-center gap-2">
              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${sourceColor}`}>
                {sourceLabel}
              </span>
              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                EDITABILITY_COLORS[field.editability].text
              } bg-white border ${EDITABILITY_COLORS[field.editability].border}`}>
                {field.editability}
              </span>
              {field.source_file && (
                <span className="text-xs text-gray-500 italic">
                  {field.source_file}
                </span>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            {/* Edit Metadata Button */}
            {!field.is_locked && field.override_source && (
              <button
                onClick={() => isEditingMetadata ? cancelEditingMetadata() : startEditingMetadata(field.id)}
                className="p-2 rounded hover:bg-gray-200 transition-colors"
                title={isEditingMetadata ? 'Cancel editing metadata' : 'Edit field metadata'}
                disabled={updating}
              >
                <Edit3 className={`size-4 ${isEditingMetadata ? 'text-blue-500' : 'text-gray-400'}`} />
              </button>
            )}

            {/* Lock Toggle */}
            {field.editability !== 'locked' && (
              <button
                onClick={() => onToggleLock?.(field.id, !field.is_locked)}
                className="p-2 rounded hover:bg-gray-200 transition-colors"
                title={field.is_locked ? 'Unlock field' : 'Lock field'}
              >
                {field.is_locked ? (
                  <Lock className="size-4 text-red-500" />
                ) : (
                  <Unlock className="size-4 text-gray-400" />
                )}
              </button>
            )}
          </div>
        </div>

        {/* Metadata Editing Section */}
        {isEditingMetadata && (
          <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <h5 className="text-sm font-medium text-blue-900 mb-3">Edit Field Metadata</h5>
            <div className="space-y-3">
              {/* Default Value */}
              <div>
                <label className="block text-xs font-medium text-blue-700 mb-1">Default Value</label>
                <input
                  type="text"
                  value={(metadataChanges.default as string) || ''}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, default: e.target.value }))}
                  placeholder="Enter default value"
                  className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* Editability */}
              <div>
                <label className="block text-xs font-medium text-blue-700 mb-1">Editability</label>
                <select
                  value={metadataChanges.editability as string || field.editability}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, editability: e.target.value }))}
                  className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="free">Free</option>
                  <option value="locked">Locked</option>
                  <option value="suggested">Suggested</option>
                  <option value="defaulted">Defaulted</option>
                </select>
              </div>

              {/* Visibility */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id={`hidden-${field.id}`}
                  checked={metadataChanges.hidden as boolean || false}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, hidden: e.target.checked }))}
                  className="rounded border-blue-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor={`hidden-${field.id}`} className="text-xs font-medium text-blue-700">
                  Hidden
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => handleMetadataUpdate(field.id, metadataChanges)}
                  disabled={updating}
                  className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {updating ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={cancelEditingMetadata}
                  disabled={updating}
                  className="px-3 py-1 bg-gray-300 text-gray-700 text-xs rounded hover:bg-gray-400 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Field Value Display/Edit */}
        <div className="mt-2">
          {canEdit ? (
            renderEditableInput(field, displayValue, (value) =>
              onFieldChange?.(field.id, value)
            )
          ) : (
            <div className="rounded px-3 py-2 bg-white border border-gray-300 text-sm text-gray-700">
              <div className="flex items-start gap-2">
                {field.is_locked && <AlertCircle className="size-4 text-red-500 mt-0.5 flex-shrink-0" />}
                <code className="break-all">
                  {typeof displayValue === 'string'
                    ? displayValue || '(empty)'
                    : JSON.stringify(displayValue, null, 2)}
                </code>
              </div>
            </div>
          )}
        </div>

        {/* Presets Section */}
        {field.presets && field.presets.length > 0 && canEdit && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-xs font-medium text-gray-600 mb-2">Quick Apply:</p>
            <div className="flex flex-wrap gap-2">
              {field.presets.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    const newValue =
                      preset.mode === 'append' && typeof displayValue === 'string'
                        ? displayValue + preset.value
                        : preset.value
                    onFieldChange?.(field.id, newValue)
                  }}
                  className="px-3 py-1 rounded text-xs bg-white border border-gray-300 hover:border-indigo-400 hover:bg-indigo-50 transition-colors"
                  title={preset.description}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderEditableInput = (
    field: EditableField,
    value: unknown,
    onChange: (value: unknown) => void
  ) => {
    const commonClasses =
      'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent'

    switch (field.type) {
      case 'text':
        return (
          <input
            type="text"
            value={(value as string) || ''}
            onChange={e => onChange(e.target.value)}
            placeholder={field.placeholder}
            className={commonClasses}
          />
        )

      case 'textarea':
        return (
          <textarea
            value={(value as string) || ''}
            onChange={e => onChange(e.target.value)}
            placeholder={field.placeholder}
            rows={field.rows || 4}
            className={commonClasses}
          />
        )

      case 'select':
        return (
          <select
            value={(value as string) || ''}
            onChange={e => onChange(e.target.value)}
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

      case 'multi_select': {
        const selectedValues = Array.isArray(value) ? value : []
        return (
          <div className="space-y-2">
            {field.options?.map(opt => (
              <label key={opt.value} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedValues.includes(opt.value)}
                  onChange={e => {
                    const newValues = e.target.checked
                      ? [...selectedValues, opt.value]
                      : selectedValues.filter((v: string) => v !== opt.value)
                    onChange(newValues)
                  }}
                  className="rounded border-gray-300"
                />
                <span className="text-sm">{opt.label}</span>
                {opt.description && (
                  <span className="text-xs text-gray-500">({opt.description})</span>
                )}
              </label>
            ))}
          </div>
        )
      }

      case 'checkbox':
        return (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={(value as boolean) || false}
              onChange={e => onChange(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600"
            />
            <span className="text-sm text-gray-700">Enabled</span>
          </label>
        )

      default:
        return (
          <div className="text-sm text-gray-500 italic">
            Unsupported field type: {field.type}
          </div>
        )
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      {/* Step Header */}
      <div className="border-b border-gray-200 pb-4">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">{step.title}</h2>
        {step.description && (
          <p className="text-sm text-gray-600 mb-3">{step.description}</p>
        )}

        {/* Stats Bar */}
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Total Fields:</span>
            <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">
              {source_tracking.total_fields}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Overridden:</span>
            <span className="px-2 py-1 rounded bg-indigo-100 text-indigo-700">
              {source_tracking.overridden_fields}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Locked:</span>
            <span className="px-2 py-1 rounded bg-red-100 text-red-700">
              {source_tracking.locked_fields}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Using Defaults:</span>
            <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">
              {source_tracking.default_fields}
            </span>
          </div>
        </div>

        {/* Source Breakdown */}
        <div className="mt-3 text-xs text-gray-600">
          <p className="font-medium mb-1">Fields by Source:</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(source_tracking.by_source).map(([source, count]) => (
              <span
                key={source}
                className={`px-2 py-1 rounded ${SOURCE_COLORS[source] || SOURCE_COLORS.base}`}
              >
                {source}: {count}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Field Groups */}
      <div className="space-y-4">
        {/* Overridden Fields */}
        {groupedFields.overridden.length > 0 && (
          <FieldGroup
            title="Overridden Fields"
            count={groupedFields.overridden.length}
            isExpanded={expandedGroups.overridden}
            onToggle={() => toggleGroup('overridden')}
            icon="indigo"
          >
            <div className="space-y-3">
              {groupedFields.overridden.map(field => renderField(field))}
            </div>
          </FieldGroup>
        )}

        {/* Locked Fields */}
        {groupedFields.locked.length > 0 && (
          <FieldGroup
            title="Locked Fields"
            count={groupedFields.locked.length}
            isExpanded={expandedGroups.locked}
            onToggle={() => toggleGroup('locked')}
            icon="red"
          >
            <div className="space-y-3">
              {groupedFields.locked.map(field => renderField(field))}
            </div>
          </FieldGroup>
        )}

        {/* Suggested Fields */}
        {groupedFields.suggested.length > 0 && (
          <FieldGroup
            title="Suggested Fields"
            count={groupedFields.suggested.length}
            isExpanded={expandedGroups.suggested}
            onToggle={() => toggleGroup('suggested')}
            icon="amber"
          >
            <div className="space-y-3">
              {groupedFields.suggested.map(field => renderField(field))}
            </div>
          </FieldGroup>
        )}

        {/* Default Fields */}
        {groupedFields.default.length > 0 && (
          <FieldGroup
            title="Default Fields"
            count={groupedFields.default.length}
            isExpanded={expandedGroups.default}
            onToggle={() => toggleGroup('default')}
            icon="gray"
          >
            <div className="space-y-3">
              {groupedFields.default.map(field => renderField(field))}
            </div>
          </FieldGroup>
        )}

        {/* Empty State */}
        {Object.values(groupedFields).every(g => g.length === 0) && (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
            <p>No fields available for this step.</p>
          </div>
        )}
      </div>
    </div>
  )
}

// Helper component for field groups
interface FieldGroupProps {
  title: string
  count: number
  isExpanded: boolean
  onToggle: () => void
  icon: 'indigo' | 'red' | 'amber' | 'gray'
  children: React.ReactNode
}

function FieldGroup({ title, count, isExpanded, onToggle, icon, children }: FieldGroupProps) {
  const iconColors = {
    indigo: 'bg-indigo-100 text-indigo-700',
    red: 'bg-red-100 text-red-700',
    amber: 'bg-amber-100 text-amber-700',
    gray: 'bg-gray-100 text-gray-700',
  }

  return (
    <div className={`rounded-lg border overflow-hidden ${
      isExpanded ? 'border-gray-300' : 'border-gray-200'
    }`}>
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between p-4 transition-colors ${
          isExpanded ? 'bg-gray-50 border-b border-gray-200' : 'hover:bg-gray-50'
        }`}
      >
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
            iconColors[icon]
          }`}>
            {count}
          </span>
        </div>
        <ChevronDown
          className={`size-5 text-gray-500 transition-transform ${
            isExpanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isExpanded && <div className="p-4">{children}</div>}
    </div>
  )
}

// Helper function to group fields by status
function groupFieldsByStatus(
  fields: EditableField[]
): Record<FieldGroup, EditableField[]> {
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
