import React, { useState } from 'react'
import { Lock, Unlock, AlertCircle, CheckCircle2, ChevronDown, Edit3, RotateCcw } from 'lucide-react'
import type { EditableField, EditableStep, Editability } from '@/types/wizard'
import { updateFieldMetadata, resetFieldToBase } from '@/api/wizardApi'
import { PresetManagement } from './PresetManagement'
import { RepeatableGroupField } from './fields/RepeatableGroupField'
import { FieldDetailsPanel } from './FieldDetailsPanel'

interface StepFieldEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown, source?: string) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
  tool: string
  language: string
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
  preset: 'bg-orange-100 text-orange-700',
}

export function StepFieldEditor({
  editableStep,
  onFieldChange,
  onMetadataUpdate,
  tool,
  language,
}: StepFieldEditorProps) {
  const { step, source_tracking } = editableStep
  const [expandedGroups, setExpandedGroups] = useState<Record<FieldGroup, boolean>>({
    overridden: true,
    default: true,
    locked: true,
    suggested: true,
  })
  const [editingMetadata, setEditingMetadata] = useState<string | null>(null)
  const [metadataChanges, setMetadataChanges] = useState<Record<string, unknown>>({})
  const [updating, setUpdating] = useState(false)
  const [showPresetManagement, setShowPresetManagement] = useState<Record<string, boolean>>({})

  const toggleGroup = (group: FieldGroup) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }))
  }

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

  const handleLockToggle = async (field: EditableField) => {
    if (!field.override_source) return

    const newLockedState = !field.is_locked
    
    if (newLockedState) {
      // When locking, open the metadata editor to allow setting the reason
      startEditingMetadata(field.id)
      setMetadataChanges(prev => ({
        ...prev,
        editability: 'locked',
        lock_reason: field.lock_reason || '',
      }))
    } else {
      // When unlocking, directly update without opening editor
      const changes: Record<string, unknown> = {
        editability: 'free',
        lock_reason: '',
      }

      // Parse override_source like "language:python" or "tool:claude"
      const [scope, target] = field.override_source.split(':', 2)
      if (!scope || !target) return

      try {
        setUpdating(true)
        const updatedStep = await updateFieldMetadata(scope, target, step.id, field.id, changes)
        onMetadataUpdate?.(updatedStep)
      } catch (error) {
        console.error('Failed to unlock field:', error)
      } finally {
        setUpdating(false)
      }
    }
  }

  const handleResetToBase = async (field: EditableField) => {
    if (!field.override_source) return

    // Parse override_source like "language:python" or "tool:claude"
    const [scope, target] = field.override_source.split(':', 2)
    if (!scope || !target) return

    try {
      setUpdating(true)
      const updatedStep = await resetFieldToBase(scope, target, step.id, field.id)
      onMetadataUpdate?.(updatedStep)
    } catch (error) {
      console.error('Failed to reset field to base:', error)
    } finally {
      setUpdating(false)
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
      lock_reason: field.lock_reason || '',
    })
  }

  const cancelEditingMetadata = () => {
    setEditingMetadata(null)
    setMetadataChanges({})
  }

  const getSourceLabel = (field: EditableField): string => {
    // If current value has a specific source (e.g., from preset application)
    if (field.current_value_source) {
      return field.current_value_source
    }
    
    // Parse override_source
    if (field.override_source) {
      if (field.override_source === 'schema') return 'base'
      if (field.override_source.startsWith('tool:')) return 'tool'
      if (field.override_source.startsWith('language:')) return 'language'
      if (field.override_source.startsWith('override:')) return 'override'
      return field.override_source
    }
    
    // Fallback to source_file parsing
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
        className={`flex flex-col gap-4 p-6 rounded-lg border-l-4 transition-all shadow-sm hover:shadow-md ${
          EDITABILITY_COLORS[field.editability].bg
        } border-b ${EDITABILITY_COLORS[field.editability].border}`}
      >
        {/* Field Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Field Title */}
            <div className="flex items-center gap-2 mb-2">
              <h4 className="font-semibold text-gray-900 text-lg">{field.label}</h4>
              {field.required && <span className="text-red-500 text-lg font-bold">*</span>}
              {field.is_locked && (
                <span title={field.lock_reason ? `Locked: ${field.lock_reason}` : "This field is locked"}>
                  <Lock className="size-5 text-red-500 flex-shrink-0" />
                </span>
              )}
              {field.is_default && (
                <span title="Using default value">
                  <CheckCircle2 className="size-5 text-green-500 flex-shrink-0" />
                </span>
              )}
            </div>

            {/* Field Description - More Prominent */}
            {field.description && (
              <p className="text-sm text-gray-700 mb-3 leading-relaxed bg-white bg-opacity-50 px-3 py-2 rounded border-l-2 border-blue-200">
                {field.description}
              </p>
            )}
          </div>

          {/* Quick Status Badge */}
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            <span
              className={`inline-block px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${sourceColor}`}
              title={`Field source: ${sourceLabel}`}
            >
              {sourceLabel}
            </span>
          </div>
        </div>

        {/* Field Details Panel */}
        <div className="pt-2 border-t border-opacity-20 border-gray-400">
          <FieldDetailsPanel
            field={field}
            sourceLabel={sourceLabel}
            onLockToggle={handleLockToggle}
            onResetToBase={handleResetToBase}
            onEditMetadata={startEditingMetadata}
            isUpdating={updating}
            canEdit={canEdit}
          />
        </div>

        {/* Metadata Editing Section */}
        {isEditingMetadata && (
          <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-lg shadow-sm">
            <h5 className="text-sm font-semibold text-blue-900 mb-4">Edit Field Metadata</h5>
            <div className="space-y-4">
              {/* Default Value */}
              <div>
                <label className="block text-sm font-medium text-blue-900 mb-2">Default Value</label>
                <input
                  type="text"
                  value={(metadataChanges.default as string) || ''}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, default: e.target.value }))}
                  placeholder="Enter default value"
                  className="w-full px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Editability */}
              <div>
                <label className="block text-sm font-medium text-blue-900 mb-2">Editability</label>
                <select
                  value={metadataChanges.editability as string || field.editability}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, editability: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="free">Free</option>
                  <option value="locked">Locked</option>
                  <option value="suggested">Suggested</option>
                  <option value="defaulted">Defaulted</option>
                </select>
              </div>

              {/* Lock Reason */}
              <div>
                <label className="block text-sm font-medium text-blue-900 mb-2">Lock Reason</label>
                <input
                  type="text"
                  value={(metadataChanges.lock_reason as string) || ''}
                  onChange={e => setMetadataChanges(prev => ({ ...prev, lock_reason: e.target.value }))}
                  placeholder="Reason for locking this field"
                  className="w-full px-3 py-2 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4 border-t border-blue-200">
                <button
                  onClick={() => handleMetadataUpdate(field.id, metadataChanges)}
                  disabled={updating}
                  className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {updating ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={cancelEditingMetadata}
                  disabled={updating}
                  className="px-4 py-2 bg-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-400 disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Field Value Display/Edit - Improved Spacing */}
        <div className="mt-4 pt-4 border-t border-opacity-20 border-gray-400">
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">
            Value
          </label>
          {canEdit ? (
            renderEditableInput(field, displayValue, (value) =>
              onFieldChange?.(field.id, value)
            )
          ) : (
            <div className="rounded-lg px-4 py-3 bg-white border border-gray-300 text-sm text-gray-700 shadow-sm">
              <div className="flex items-start gap-3">
                {field.is_locked && <AlertCircle className="size-5 text-red-500 mt-0.5 flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <code className="break-all text-xs bg-gray-50 px-2 py-1 rounded block">
                    {typeof displayValue === 'string'
                      ? displayValue || '(empty)'
                      : JSON.stringify(displayValue, null, 2)}
                  </code>
                  {field.is_locked && field.lock_reason && (
                    <div className="mt-2 text-xs text-red-600 italic bg-red-50 px-3 py-2 rounded">
                      <strong>Locked:</strong> {field.lock_reason}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Presets Section - Improved Spacing */}
        {field.presets && field.presets.length > 0 && canEdit && (
          <div className="mt-4 pt-4 border-t border-opacity-20 border-gray-400">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Quick Apply:</p>
              <button
                onClick={() => setShowPresetManagement(prev => ({
                  ...prev,
                  [field.id]: !prev[field.id]
                }))}
                className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors font-medium"
              >
                Manage Presets
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {field.presets.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    const newValue =
                      preset.mode === 'append' && typeof displayValue === 'string'
                        ? displayValue + preset.value
                        : preset.value
                    onFieldChange?.(field.id, newValue, 'preset')
                  }}
                  className="px-3 py-2 rounded-md text-xs bg-white border border-gray-300 hover:border-indigo-400 hover:bg-indigo-50 transition-colors font-medium"
                  title={preset.description}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Preset Management */}
        {showPresetManagement[field.id] && (
          <div className="mt-4 pt-4 border-t border-opacity-20 border-gray-400">
            <PresetManagement
              tool={tool}
              language={language}
              fieldId={field.id}
              onAssignmentsChange={(assignments) => {
                console.log('Preset assignments updated:', assignments)
              }}
            />
          </div>
        )}
      </div>
    )
  }

  const renderEditableInput = (
    field: {
      type: string
      placeholder?: string
      rows?: number
      options?: { value: string; label: string; description?: string }[]
      description?: string
      fields?: any[]
    },
    value: unknown,
    onChange: (value: unknown) => void
  ) => {
    const commonClasses =
      'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-base shadow-sm transition-shadow hover:shadow-md'

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

      case 'number':
        return (
          <input
            type="number"
            value={(value as number) || ''}
            onChange={e => onChange(e.target.value ? Number(e.target.value) : '')}
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
            className={`${commonClasses} resize-vertical font-mono text-sm`}
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
              onChange={e => onChange(e.target.checked)}
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
            onChange={onChange}
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

  return (
    <div className="flex flex-col gap-8 max-w-5xl">
      {/* Step Header */}
      <div className="border-b border-gray-200 pb-6">
        <h2 className="text-3xl font-bold text-gray-900 mb-3">{step.title}</h2>
        {step.description && (
          <p className="text-base text-gray-600 mb-6 leading-relaxed">{step.description}</p>
        )}

        {/* Stats Bar - Improved Styling */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-100 shadow-sm">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Total Fields</span>
              <span className="px-3 py-2 rounded-lg bg-white border border-gray-200 text-gray-900 font-bold text-lg">
                {source_tracking.total_fields}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Overridden</span>
              <span className="px-3 py-2 rounded-lg bg-indigo-100 text-indigo-900 font-bold text-lg border border-indigo-200">
                {source_tracking.overridden_fields}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Locked</span>
              <span className="px-3 py-2 rounded-lg bg-red-100 text-red-900 font-bold text-lg border border-red-200">
                {source_tracking.locked_fields}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Using Defaults</span>
              <span className="px-3 py-2 rounded-lg bg-gray-100 text-gray-900 font-bold text-lg border border-gray-200">
                {source_tracking.default_fields}
              </span>
            </div>
          </div>
        </div>

        {/* Source Breakdown */}
        <div className="mt-6">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Fields by Source</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(source_tracking.by_source).map(([source, count]) => (
              <span
                key={source}
                className={`px-4 py-2 rounded-lg font-medium text-sm shadow-sm ${
                  SOURCE_COLORS[source] || SOURCE_COLORS.base
                }`}
              >
                {source}: {count}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Field Groups - Improved Spacing */}
      <div className="space-y-6">
        {/* Overridden Fields */}
        {groupedFields.overridden.length > 0 && (
          <FieldGroup
            title="Overridden Fields"
            count={groupedFields.overridden.length}
            isExpanded={expandedGroups.overridden}
            onToggle={() => toggleGroup('overridden')}
            icon="indigo"
          >
            <div className="space-y-4">
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
            <div className="space-y-4">
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
            <div className="space-y-4">
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
            <div className="space-y-4">
              {groupedFields.default.map(field => renderField(field))}
            </div>
          </FieldGroup>
        )}

        {/* Empty State */}
        {Object.values(groupedFields).every(g => g.length === 0) && (
          <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center text-gray-500 bg-gray-50">
            <p className="text-lg font-medium">No fields available for this step.</p>
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

  const borderColors = {
    indigo: 'border-l-indigo-600',
    red: 'border-l-red-600',
    amber: 'border-l-amber-600',
    gray: 'border-l-gray-400',
  }

  return (
    <div
      className={`rounded-lg border-l-4 overflow-hidden shadow transition-all ${
        borderColors[icon]
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
              iconColors[icon]
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
