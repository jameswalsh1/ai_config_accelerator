import React, { useState, useEffect } from 'react'
import { Lock, Unlock, ChevronDown, RotateCcw, Loader2, AlertCircle } from 'lucide-react'
import type { EditableField, EditableStep, Editability } from '@/types/wizard'
import { updateFieldMetadata, resetFieldToBase } from '@/api/wizardApi'
import { PresetManagement } from './PresetManagement'
import { RepeatableGroupField } from './fields/RepeatableGroupField'

interface StepFieldEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown, source?: string) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
  onFieldSave?: (fieldId: string, value: unknown) => Promise<void>
  tool: string
  language: string
}

type FieldGroup = 'overridden' | 'default' | 'locked' | 'suggested'

const EDITABILITY_COLORS: Record<Editability, { bg: string; border: string; text: string }> = {
  free: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700' },
  // 'locked' in the editor means the field will be locked for wizard users — amber, not red,
  // because the SME here can always edit it.
  locked: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' },
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
  onFieldSave,
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
  const [updating, setUpdating] = useState(false)
  const [showPresetManagement, setShowPresetManagement] = useState<Record<string, boolean>>({})
  // Per-field inline edit state for default value and lock reason (saved on blur)
  const [inlineEdits, setInlineEdits] = useState<Record<string, { default?: string; lock_reason?: string }>>({})
  // Draft values for the live value inputs (so we have stable controlled inputs and only save on blur/change)
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(step.fields.map(f => [f.id, f.current_value ?? f.default ?? '']))
  )
  // Which fields are currently being persisted
  const [savingFields, setSavingFields] = useState<Set<string>>(new Set())
  // Per-field inline validation errors (e.g. malformed JSON)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  // When the step changes (new step loaded), reset draft values and errors
  useEffect(() => {
    setFieldValues(Object.fromEntries(step.fields.map(f => [f.id, f.current_value ?? f.default ?? ''])))
    setInlineEdits({})
    setFieldErrors({})
  }, [step.id])

  const toggleGroup = (group: FieldGroup) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }))
  }

  // Save a field value to the backend immediately
  const handleValueSave = async (fieldId: string, value: unknown) => {
    if (!onFieldSave) return
    setSavingFields(prev => new Set([...prev, fieldId]))
    try {
      await onFieldSave(fieldId, value)
    } finally {
      setSavingFields(prev => { const s = new Set(prev); s.delete(fieldId); return s })
    }
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
      // Clear any stale inline edit state for this field
      setInlineEdits(prev => {
        const next = { ...prev }
        delete next[fieldId]
        return next
      })
    } catch (error) {
      console.error('Failed to update metadata:', error)
    } finally {
      setUpdating(false)
    }
  }

  const handleLockToggle = async (field: EditableField) => {
    if (!field.override_source) return
    const [scope, target] = field.override_source.split(':', 2)
    if (!scope || !target) return
    const newLockedState = !field.is_locked
    const changes: Record<string, unknown> = {
      editability: newLockedState ? 'locked' : 'free',
      lock_reason: newLockedState ? (field.lock_reason || '') : '',
    }
    try {
      setUpdating(true)
      const updatedStep = await updateFieldMetadata(scope, target, step.id, field.id, changes)
      onMetadataUpdate?.(updatedStep)
    } catch (error) {
      console.error('Failed to toggle lock:', error)
    } finally {
      setUpdating(false)
    }
  }

  const handleResetToBase = async (field: EditableField) => {
    if (!field.override_source) return
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

  // ---------------------------------------------------------------------------
  // Inline validation helpers
  // ---------------------------------------------------------------------------

  /**
   * Try to parse `raw` as JSON. Returns an error string on failure, null on success.
   * Empty / whitespace-only strings are always considered valid (field is just blank).
   */
  const validateJson = (raw: string): string | null => {
    const trimmed = raw.trim()
    if (!trimmed) return null
    try {
      JSON.parse(trimmed)
      return null
    } catch (e) {
      return e instanceof SyntaxError ? e.message : 'Invalid JSON'
    }
  }

  /**
   * Decide whether a text/textarea field's value should be validated as JSON.
   * Rules (in priority order):
   *   1. Field id contains "json"  →  always validate as JSON
   *   2. Trimmed value starts with { or [  →  opportunistic: user clearly intends JSON
   */
  const shouldValidateAsJson = (fieldId: string, value: string): boolean => {
    if (/_?json_?/i.test(fieldId)) return true
    const t = value.trim()
    return t.startsWith('{') || t.startsWith('[')
  }

  const handleFieldBlurValidation = (fieldId: string, value: string) => {
    if (!shouldValidateAsJson(fieldId, value)) {
      // Clear any stale error if the value no longer looks like JSON
      setFieldErrors(prev => {
        if (!prev[fieldId]) return prev
        const next = { ...prev }
        delete next[fieldId]
        return next
      })
      return
    }
    const err = validateJson(value)
    setFieldErrors(prev => {
      if (!err) {
        if (!prev[fieldId]) return prev
        const next = { ...prev }
        delete next[fieldId]
        return next
      }
      return { ...prev, [fieldId]: err }
    })
  }

  const getSourceLabel = (field: EditableField): string => {    // If current value has a specific source (e.g., from preset application)
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
    const displayValue = field.current_value ?? field.default ?? ''
    const colors = EDITABILITY_COLORS[field.editability] || EDITABILITY_COLORS.free
    // override_source of 'schema' means base-only; no writes possible
    const hasOverride = !!field.override_source && field.override_source !== 'schema'
    const isLocked = field.is_locked

    // Inline edit state for default value and lock reason (save on blur)
    const fieldEdits = inlineEdits[field.id] || {}
    const rawDefault = field.default !== undefined
      ? (typeof field.default === 'string' ? field.default : JSON.stringify(field.default))
      : ''
    const localDefault = fieldEdits.default !== undefined ? fieldEdits.default : rawDefault
    const localLockReason = fieldEdits.lock_reason !== undefined ? fieldEdits.lock_reason : (field.lock_reason || '')

    return (
      <div
        key={field.id}
        className={`rounded-lg border border-l-4 shadow-sm overflow-hidden ${colors.bg} ${colors.border}`}
      >
        {/* ── Header: label + editability dropdown + lock toggle + reset ── */}
        <div className="flex items-start gap-3 px-4 py-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h4 className="font-semibold text-gray-900">{field.label}</h4>
              {field.required && <span className="text-red-500 font-bold leading-none">*</span>}
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${sourceColor}`}
                title={`Source: ${sourceLabel}`}
              >
                {sourceLabel}
              </span>
            </div>
            {field.description && (
              <p className="text-sm text-gray-600 mt-0.5 leading-snug">{field.description}</p>
            )}
          </div>

          {/* Controls: editability select + lock toggle + reset */}
          <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
            {hasOverride ? (
              <select
                value={field.editability}
                onChange={e => handleMetadataUpdate(field.id, { editability: e.target.value })}
                disabled={updating}
                title="How wizard users can interact with this field"
                className={`text-xs px-2 py-1 rounded border font-medium cursor-pointer bg-white disabled:opacity-50 focus:outline-none focus:ring-1 focus:ring-indigo-400 ${colors.border} ${colors.text}`}
              >
                <option value="free">Free</option>
                <option value="suggested">Suggested</option>
                <option value="defaulted">Defaulted</option>
                <option value="locked">Locked</option>
              </select>
            ) : (
              <span className={`text-xs px-2 py-1 rounded border font-medium bg-white ${colors.border} ${colors.text}`}>
                {field.editability}
              </span>
            )}

            {hasOverride && (
              <button
                onClick={() => handleLockToggle(field)}
                disabled={updating}
                title={isLocked ? 'Unlock for wizard users' : 'Lock for wizard users'}
                className={`p-1.5 rounded border transition-colors disabled:opacity-50 ${
                  isLocked
                    ? 'bg-amber-100 border-amber-300 text-amber-700 hover:bg-amber-200'
                    : 'bg-white border-gray-300 text-gray-400 hover:bg-gray-100 hover:text-gray-600'
                }`}
              >
                {isLocked ? <Lock className="size-3.5" /> : <Unlock className="size-3.5" />}
              </button>
            )}

            {hasOverride && (
              <button
                onClick={() => handleResetToBase(field)}
                disabled={updating}
                title="Reset to base configuration"
                className="p-1.5 rounded border bg-white border-gray-300 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors disabled:opacity-50"
              >
                <RotateCcw className="size-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* ── Lock reason bar (only when locked) ── */}
        {isLocked && (
          <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border-t border-amber-200">
            <Lock className="size-3.5 text-amber-600 shrink-0" />
            <span className="text-xs font-medium text-amber-700 shrink-0 w-14">Reason:</span>
            {hasOverride ? (
              <input
                type="text"
                value={localLockReason}
                onChange={e =>
                  setInlineEdits(prev => ({
                    ...prev,
                    [field.id]: { ...prev[field.id], lock_reason: e.target.value },
                  }))
                }
                onBlur={() => {
                  if (localLockReason !== (field.lock_reason || '')) {
                    handleMetadataUpdate(field.id, { lock_reason: localLockReason })
                  }
                }}
                placeholder="Explain why this field is locked for users…"
                className="flex-1 text-xs px-2 py-1 bg-white border border-amber-300 rounded focus:outline-none focus:ring-1 focus:ring-amber-400"
              />
            ) : (
              <span className="text-xs text-amber-800 italic">
                {field.lock_reason || 'No reason specified'}
              </span>
            )}
          </div>
        )}

        {/* ── Default value row (inline editable, saves on blur) ── */}
        {hasOverride && (
          <div className="flex items-start gap-2 px-4 py-2 bg-white border-t border-gray-100">
            <span className="text-xs font-medium text-gray-500 w-14 shrink-0 mt-1.5">Default:</span>
            <div className="flex-1 min-w-0">
              <input
                type="text"
                value={localDefault}
                onChange={e =>
                  setInlineEdits(prev => ({
                    ...prev,
                    [field.id]: { ...prev[field.id], default: e.target.value },
                  }))
                }
                onBlur={() => {
                  // Validate JSON if needed before saving
                  const jsonErr = shouldValidateAsJson(field.id, localDefault)
                    ? validateJson(localDefault)
                    : null
                  const errorKey = `${field.id}__default`
                  setFieldErrors(prev => {
                    if (!jsonErr) {
                      const next = { ...prev }; delete next[errorKey]; return next
                    }
                    return { ...prev, [errorKey]: jsonErr }
                  })
                  if (!jsonErr && localDefault !== rawDefault) {
                    handleMetadataUpdate(field.id, { default: localDefault })
                  }
                }}
                placeholder="No default set"
                className={`w-full text-xs px-2 py-1.5 border rounded focus:outline-none focus:ring-1 ${
                  fieldErrors[`${field.id}__default`]
                    ? 'border-red-400 focus:ring-red-400 bg-red-50'
                    : 'border-gray-200 focus:ring-indigo-400'
                }`}
              />
              {fieldErrors[`${field.id}__default`] && (
                <p className="flex items-center gap-1 mt-1 text-xs text-red-600">
                  <AlertCircle className="size-3 shrink-0" />
                  {fieldErrors[`${field.id}__default`]}
                </p>
              )}
            </div>
          </div>
        )}

        {/* ── Current value (auto-save on blur / change) ── */}
        <div className="px-4 py-3 border-t border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Value
            </label>
            {savingFields.has(field.id) && (
              <span className="inline-flex items-center gap-1 text-xs text-indigo-600">
                <Loader2 className="size-3 animate-spin" />
                Saving…
              </span>
            )}
          </div>
          {renderEditableInput(
            field,
            fieldValues[field.id] ?? displayValue,
            (value) => {
              setFieldValues(prev => ({ ...prev, [field.id]: value }))
              onFieldChange?.(field.id, value)
            },
            (value) => handleValueSave(field.id, value)
          )}
        </div>

        {/* ── Presets ── */}
        {field.presets && field.presets.length > 0 && (
          <div className="px-4 py-3 border-t border-gray-100 bg-white">
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-xs font-medium text-gray-500 shrink-0">Presets:</span>
              {field.presets.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    const currentVal = fieldValues[field.id] ?? displayValue
                    const newValue =
                      preset.mode === 'append' && typeof currentVal === 'string'
                        ? currentVal + preset.value
                        : preset.value
                    setFieldValues(prev => ({ ...prev, [field.id]: newValue }))
                    onFieldChange?.(field.id, newValue, 'preset')
                    handleValueSave(field.id, newValue)
                  }}
                  title={preset.description}
                  className="px-2.5 py-1 rounded text-xs bg-white border border-gray-300 hover:border-indigo-400 hover:bg-indigo-50 transition-colors font-medium"
                >
                  {preset.label}
                </button>
              ))}
              <button
                onClick={() =>
                  setShowPresetManagement(prev => ({ ...prev, [field.id]: !prev[field.id] }))
                }
                className="ml-auto text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded border border-gray-200 hover:bg-gray-200 transition-colors shrink-0"
              >
                {showPresetManagement[field.id] ? 'Hide' : 'Manage Presets'}
              </button>
            </div>
          </div>
        )}

        {/* Preset Management panel */}
        {showPresetManagement[field.id] && (
          <div className="px-4 py-3 border-t border-gray-200">
            <PresetManagement
              tool={tool}
              language={language}
              fieldId={field.id}
              onAssignmentsChange={assignments => {
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
      id: string
      type: string
      placeholder?: string
      rows?: number
      options?: { value: string; label: string; description?: string }[]
      description?: string
      fields?: any[]
    },
    value: unknown,
    onChange: (value: unknown) => void,
    onSave: (value: unknown) => void
  ) => {
    const fieldId = field.id
    const validationError = fieldErrors[fieldId]
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
                handleFieldBlurValidation(fieldId, e.target.value)
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
                handleFieldBlurValidation(fieldId, e.target.value)
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
