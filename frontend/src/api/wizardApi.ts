import type { WizardAnswers, WizardConfig, WizardConfigSummary, EditableStep, Preset, PresetAssignment } from '@/types/wizard'

const BASE = 'http://localhost:8001'

export type { EditableStep }

export async function fetchConfigs(): Promise<WizardConfigSummary[]> {
  const res = await fetch(`${BASE}/api/wizard/configs`)
  if (!res.ok) throw new Error(`Failed to load configs: ${res.statusText}`)
  return res.json() as Promise<WizardConfigSummary[]>
}

export async function fetchWizardConfig(id: string): Promise<WizardConfig> {
  const res = await fetch(`${BASE}/api/wizard/config/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error(`Failed to load config '${id}': ${res.statusText}`)
  return res.json() as Promise<WizardConfig>
}

export async function generateFiles(configId: string, answers: WizardAnswers): Promise<void> {
  const res = await fetch(`${BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id: configId, answers }),
  })
  if (!res.ok) throw new Error(`Generation failed: ${res.statusText}`)

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${configId}_config.zip`
  anchor.click()
  URL.revokeObjectURL(url)
}

export interface ToolOption {
  id: string
  title: string
  description: string
  target: string
}

export interface LanguageOption {
  id: string
  title: string
  description: string
}

export interface StepOption {
  id: string
  title: string
  description: string
}

export async function fetchAvailableTools(): Promise<ToolOption[]> {
  const res = await fetch(`${BASE}/config/tools`)
  if (!res.ok) throw new Error(`Failed to load tools: ${res.statusText}`)
  return res.json() as Promise<ToolOption[]>
}

export async function fetchAvailableLanguages(): Promise<LanguageOption[]> {
  const res = await fetch(`${BASE}/config/languages`)
  if (!res.ok) throw new Error(`Failed to load languages: ${res.statusText}`)
  return res.json() as Promise<LanguageOption[]>
}

export async function fetchAvailableSteps(tool: string, language: string): Promise<StepOption[]> {
  const res = await fetch(`${BASE}/config/steps?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}`)
  if (!res.ok) throw new Error(`Failed to load steps: ${res.statusText}`)
  return res.json() as Promise<StepOption[]>
}

export async function fetchEditableConfig(tool: string, language: string, stepId: string): Promise<EditableStep> {
  const res = await fetch(`${BASE}/config/edit?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}&step_id=${encodeURIComponent(stepId)}`)
  if (!res.ok) throw new Error(`Failed to load editable config: ${res.statusText}`)
  return res.json() as Promise<EditableStep>
}

export async function updateFieldMetadata(
  scope: string,
  target: string,
  stepId: string,
  fieldId: string,
  changes: Record<string, unknown>
): Promise<EditableStep> {
  const res = await fetch(`${BASE}/config/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope,
      target,
      step_id: stepId,
      field_id: fieldId,
      changes,
    }),
  })
  if (!res.ok) throw new Error(`Failed to update field metadata: ${res.statusText}`)
  return res.json() as Promise<EditableStep>
}

export async function resetFieldToBase(
  scope: string,
  target: string,
  stepId: string,
  fieldId: string,
  overrideType: 'metadata' | 'structure' = 'metadata'
): Promise<EditableStep> {
  const res = await fetch(`${BASE}/config/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope,
      target,
      step_id: stepId,
      field_id: fieldId,
      override_type: overrideType,
    }),
  })
  if (!res.ok) throw new Error(`Failed to reset field to base: ${res.statusText}`)
  return res.json() as Promise<EditableStep>
}

export async function fetchAvailablePresets(tool: string, language: string): Promise<{
  shared: Preset[]
  language: Preset[]
  tool: Preset[]
}> {
  const res = await fetch(`${BASE}/api/wizard/presets?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}`)
  if (!res.ok) throw new Error(`Failed to load presets: ${res.statusText}`)
  return res.json() as Promise<{
    shared: Preset[]
    language: Preset[]
    tool: Preset[]
  }>
}

export async function fetchFieldPresetAssignments(
  tool: string,
  language: string,
  fieldId: string
): Promise<PresetAssignment[]> {
  const res = await fetch(`${BASE}/api/wizard/field-presets?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}&field_id=${encodeURIComponent(fieldId)}`)
  if (!res.ok) throw new Error(`Failed to load field preset assignments: ${res.statusText}`)
  return res.json() as Promise<PresetAssignment[]>
}

export async function assignPresetToField(
  tool: string,
  language: string,
  fieldId: string,
  presetId: string,
  assignmentMode: string,
  displayOrder: number
): Promise<PresetAssignment> {
  const res = await fetch(`${BASE}/api/wizard/field-presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool,
      language,
      field_id: fieldId,
      preset_id: presetId,
      assignment_mode: assignmentMode,
      display_order: displayOrder,
    }),
  })
  if (!res.ok) throw new Error(`Failed to assign preset: ${res.statusText}`)
  return res.json() as Promise<PresetAssignment>
}

export async function updatePresetAssignment(
  assignmentId: string,
  changes: Partial<PresetAssignment>
): Promise<PresetAssignment> {
  const res = await fetch(`${BASE}/api/wizard/field-presets/${encodeURIComponent(assignmentId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
  if (!res.ok) throw new Error(`Failed to update preset assignment: ${res.statusText}`)
  return res.json() as Promise<PresetAssignment>
}

export async function removePresetFromField(assignmentId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/wizard/field-presets/${encodeURIComponent(assignmentId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to remove preset assignment: ${res.statusText}`)
}

export async function reorderPresetAssignments(
  tool: string,
  language: string,
  fieldId: string,
  assignmentIds: string[]
): Promise<void> {
  const res = await fetch(`${BASE}/api/wizard/field-presets/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool,
      language,
      field_id: fieldId,
      assignment_ids: assignmentIds,
    }),
  })
  if (!res.ok) throw new Error(`Failed to reorder preset assignments: ${res.statusText}`)
}
