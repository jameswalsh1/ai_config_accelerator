import { useState, useEffect } from 'react'
import { Lock, Unlock, RotateCcw, AlertCircle, Plus, X } from 'lucide-react'
import type { EditableField, EditableStep, Editability } from '@/types/wizard'
import { updateFieldMetadata, resetFieldToBase, addPresetToField, removePresetFromField } from '@/api/wizardApi'
import { FieldGroup, groupFieldsByStatus, type FieldGroupKey } from './FieldGroup'
import { FieldValueInput } from './FieldValueInput'

interface StepFieldEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown, source?: string) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
  onFieldSave?: (fieldId: string, value: unknown) => Promise<void>
  tool: string
  language: string
  hiddenFieldIds?: Set<string>
}

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

function AddPresetForm({ onAdd, onCancel }: {
  onAdd: (label: string, value: string, mode: string) => void
  onCancel: () => void
}) {
  const [label, setLabel] = useState('')
  const [value, setValue] = useState('')
  const [mode, setMode] = useState<string>('replace')

  return (
    <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Label</label>
          <input
            type="text"
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="e.g. PEP8 + Black"
            className="w-full text-sm px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Mode</label>
          <select
            value={mode}
            onChange={e => setMode(e.target.value)}
            className="w-full text-sm px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
          >
            <option value="replace">Replace</option>
            <option value="append">Append</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Value</label>
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder="The value that will be applied when the user selects this preset"
          rows={3}
          className="w-full text-sm px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-vertical font-mono"
        />
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onAdd(label, value, mode)}
          disabled={!label.trim() || !value.trim()}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          Add Preset
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export function StepFieldEditor({
  editableStep,
  onFieldChange,
  onMetadataUpdate,
  onFieldSave,
  tool,
  language,
  hiddenFieldIds,
}: StepFieldEditorProps) {
  const { step, source_tracking } = editableStep
  const [expandedGroups, setExpandedGroups] = useState<Record<FieldGroupKey, boolean>>({
    overridden: true,
    default: true,
    locked: true,
    suggested: true,
  })
  const [updating, setUpdating] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showAddPreset, setShowAddPreset] = useState<Record<string, boolean>>({})
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
  }, [step.id, step.fields])

  const toggleGroup = (group: FieldGroupKey) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }))
  }

  // Track which fields saved successfully (vs errored) so UI shows correct indicator
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({})

  // Save a field value to the backend immediately
  const handleValueSave = async (fieldId: string, value: unknown) => {
    if (!onFieldSave) return
    setSavingFields(prev => new Set([...prev, fieldId]))
    setSaveErrors(prev => { const n = { ...prev }; delete n[fieldId]; return n })
    try {
      await onFieldSave(fieldId, value)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to save'
      setSaveErrors(prev => ({ ...prev, [fieldId]: msg }))
    } finally {
      setSavingFields(prev => { const s = new Set(prev); s.delete(fieldId); return s })
    }
  }

  // Resolve scope/target for a field — falls back to language scope if no override source
  const scopeForField = (field: EditableField): { scope: string; target: string } => {
    if (field.override_source && field.override_source !== 'schema') {
      const [s, t] = field.override_source.split(':', 2)
      if (s && t) return { scope: s, target: t }
    }
    return { scope: 'language', target: language }
  }

  const handleAddPreset = async (field: EditableField, label: string, value: string, mode: string) => {
    const { scope, target } = scopeForField(field)
    try {
      setActionError(null)
      const result = await addPresetToField(scope, target, tool, language, step.id, field.id, { label, value, mode })
      onMetadataUpdate?.(result)
      setShowAddPreset(prev => ({ ...prev, [field.id]: false }))
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to add preset'
      setActionError(msg)
    }
  }

  const handleRemovePreset = async (field: EditableField, presetLabel: string) => {
    const { scope, target } = scopeForField(field)
    try {
      setActionError(null)
      const result = await removePresetFromField(scope, target, tool, language, step.id, field.id, presetLabel)
      onMetadataUpdate?.(result)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to remove preset'
      setActionError(msg)
    }
  }

  // Group fields by status for clear organization (filter hidden fields first)
  const visibleFields = hiddenFieldIds && hiddenFieldIds.size > 0
    ? step.fields.filter(f => !hiddenFieldIds.has(f.id))
    : step.fields
  const groupedFields = groupFieldsByStatus(visibleFields)

  const handleMetadataUpdate = async (fieldId: string, changes: Record<string, unknown>) => {
    const field = step.fields.find(f => f.id === fieldId)
    if (!field || !field.override_source) return

    // Parse override_source like "language:python" or "tool:claude"
    const [scope, target] = field.override_source.split(':', 2)
    if (!scope || !target) return

    try {
      setUpdating(true)
      setActionError(null)
      const updatedStep = await updateFieldMetadata(scope, target, step.id, fieldId, changes, tool, language)
      onMetadataUpdate?.(updatedStep)
      // Clear any stale inline edit state for this field
      setInlineEdits(prev => {
        const next = { ...prev }
        delete next[fieldId]
        return next
      })
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to update metadata'
      setActionError(msg)
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
      setActionError(null)
      const updatedStep = await updateFieldMetadata(scope, target, step.id, field.id, changes, tool, language)
      onMetadataUpdate?.(updatedStep)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to toggle lock'
      setActionError(msg)
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
      setActionError(null)
      const updatedStep = await resetFieldToBase(scope, target, step.id, field.id, tool, language)
      onMetadataUpdate?.(updatedStep)
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to reset field'
      setActionError(msg)
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

    // Inline edit state for lock reason (save on blur)
    const fieldEdits = inlineEdits[field.id] || {}
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
                onChange={e => { void handleMetadataUpdate(field.id, { editability: e.target.value }) }}
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
                onClick={() => { void handleLockToggle(field) }}
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
                onClick={() => { void handleResetToBase(field) }}
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
                    void handleMetadataUpdate(field.id, { lock_reason: localLockReason })
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

        {/* ── Current value ── */}
        <div className="px-4 py-3 border-t border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Value
            </label>
          </div>
          <FieldValueInput
            field={field}
            value={fieldValues[field.id] ?? displayValue}
            onChange={(value) => {
              setFieldValues(prev => ({ ...prev, [field.id]: value }))
              onFieldChange?.(field.id, value)
            }}
            onSave={(value) => { void handleValueSave(field.id, value) }}
            isDirty={JSON.stringify(fieldValues[field.id] ?? displayValue) !== JSON.stringify(field.current_value ?? field.default ?? '')}
            isSaving={savingFields.has(field.id)}
            saveError={saveErrors[field.id]}
            validationError={fieldErrors[field.id]}
            onBlurValidation={handleFieldBlurValidation}
          />
        </div>

        {/* ── Presets ── */}
        <div className="px-4 py-3 border-t border-gray-100 bg-white">
          <div className="flex items-center flex-wrap gap-2">
            <span className="text-xs font-medium text-gray-500 shrink-0">Presets:</span>
            {field.presets && field.presets.length > 0 && field.presets.map((preset, idx) => (
              <span key={idx} className="inline-flex items-center gap-0.5 group">
                <button
                  onClick={() => {
                    const currentVal = fieldValues[field.id] ?? displayValue
                    const newValue =
                      preset.mode === 'append' && typeof currentVal === 'string'
                        ? currentVal + String(preset.value)
                        : preset.value
                    setFieldValues(prev => ({ ...prev, [field.id]: newValue }))
                    onFieldChange?.(field.id, newValue, 'preset')
                    void handleValueSave(field.id, newValue)
                  }}
                  title={preset.description || `Apply "${preset.label}"`}
                  className="px-2.5 py-1 rounded-l text-xs bg-white border border-r-0 border-gray-300 hover:border-indigo-400 hover:bg-indigo-50 transition-colors font-medium"
                >
                  {preset.label}
                </button>
                <button
                  onClick={() => { void handleRemovePreset(field, preset.label) }}
                  title={`Remove "${preset.label}" preset`}
                  className="px-1 py-1 rounded-r text-xs bg-white border border-gray-300 text-gray-400 hover:bg-red-50 hover:border-red-300 hover:text-red-500 transition-colors"
                >
                  <X className="size-3" />
                </button>
              </span>
            ))}
            {(!field.presets || field.presets.length === 0) && (
              <span className="text-xs text-gray-400 italic">No presets</span>
            )}
            <button
              onClick={() =>
                setShowAddPreset(prev => ({ ...prev, [field.id]: !prev[field.id] }))
              }
              className="ml-auto inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-indigo-50 text-indigo-600 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors shrink-0"
            >
              <Plus className="size-3" />
              Add
            </button>
          </div>

          {/* Inline Add Preset Form */}
          {showAddPreset[field.id] && (
            <AddPresetForm
              onAdd={(label, value, mode) => { void handleAddPreset(field, label, value, mode) }}
              onCancel={() => setShowAddPreset(prev => ({ ...prev, [field.id]: false }))}
            />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8 max-w-5xl">
      {/* Error Banner */}
      {actionError && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          <AlertCircle className="size-5 shrink-0 mt-0.5 text-red-500" />
          <p className="flex-1">{actionError}</p>
          <button
            onClick={() => setActionError(null)}
            className="shrink-0 text-red-400 hover:text-red-600"
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}

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
