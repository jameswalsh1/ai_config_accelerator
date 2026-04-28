import type { WizardAnswers, WizardConfig, WizardConfigSummary, EditableStep, Preset, PresetAssignment } from '@/types/wizard'

const BASE = 'http://localhost:8000'

export type { EditableStep }

export async function fetchConfigs(): Promise<WizardConfigSummary[]> {
  const res = await fetch(`${BASE}/api/wizard/configs`)
  if (!res.ok) throw new Error(`Failed to load configs: ${res.statusText}`)
  return res.json() as Promise<WizardConfigSummary[]>
}

export async function fetchWizardConfig(id: string, language?: string): Promise<WizardConfig> {
  const params = new URLSearchParams()
  if (language) params.append('language', language)
  const query = params.toString()
  const url = query 
    ? `${BASE}/api/wizard/config/${encodeURIComponent(id)}?${query}`
    : `${BASE}/api/wizard/config/${encodeURIComponent(id)}`
  const res = await fetch(url)
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

export interface PreviewFile {
  path: string
  content: string
  language: string
}

export interface PreviewResponse {
  files: PreviewFile[]
}

export async function previewFiles(configId: string, answers: WizardAnswers): Promise<PreviewResponse> {
  const res = await fetch(`${BASE}/api/generate/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id: configId, answers }),
  })
  if (!res.ok) throw new Error(`Preview failed: ${res.statusText}`)
  return res.json() as Promise<PreviewResponse>
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

export interface CreateLanguagePayload {
  language_id: string
  title: string
  description?: string
  based_on?: string
  /** Optional tag remapping applied to all presets: { oldTag: newTag } */
  tag_remap?: Record<string, string>
}

export async function createLanguageConfig(payload: CreateLanguagePayload): Promise<LanguageOption> {
  const res = await fetch(`${BASE}/config/languages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
  const data = await res.json() as { language_id: string; metadata?: { title?: string; description?: string } }
  return {
    id: data.language_id,
    title: data.metadata?.title ?? data.language_id,
    description: data.metadata?.description ?? '',
  }
}

export async function fetchLanguageTags(languageId: string): Promise<string[]> {
  const res = await fetch(`${BASE}/config/languages/${encodeURIComponent(languageId)}/tags`)
  if (!res.ok) throw new Error(`Failed to load tags: ${res.statusText}`)
  return res.json() as Promise<string[]>
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

export async function saveFieldValue(
  tool: string,
  language: string,
  stepId: string,
  fieldId: string,
  value: unknown,
  scope?: string,
  target?: string
): Promise<EditableStep> {
  const resolvedScope = scope ?? 'language'
  const resolvedTarget = target ?? language

  const res = await fetch(`${BASE}/config/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope: resolvedScope,
      target: resolvedTarget,
      step_id: stepId,
      field_id: fieldId,
      changes: {
        default: value,
      },
    }),
  })
  if (!res.ok) throw new Error(`Failed to save field value: ${res.statusText}`)
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

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export interface AuditEntry {
  timestamp: string
  action: 'create' | 'update' | 'delete'
  scope: string
  target: string
  file: string
  actor: string
  diff_summary: string
  diff: AuditDiff
}

export interface AuditDiff {
  before_id: string
  after_id: string
  has_changes: boolean
  total_changes: number
  metadata_changes: {
    title: string | null
    description: string | null
  }
  steps: {
    added: string[]
    removed: string[]
    modified: AuditStepDiff[]
  }
}

export interface AuditStepDiff {
  step_id: string
  change_type: string
  title_changed: boolean
  before_title: string | null
  after_title: string | null
  description_changed: boolean
  before_description: string | null
  after_description: string | null
  fields_added: string[]
  fields_removed: string[]
  field_diffs: AuditFieldDiff[]
}

export interface AuditFieldDiff {
  field_id: string
  field_type: string
  change_type: string
  value_changed: boolean
  before_value: unknown
  after_value: unknown
  label_changed: boolean
  before_label: string | null
  after_label: string | null
  description_changed: boolean
  preset_changes: AuditPresetChange[]
  locking_changes: AuditLockingChange | null
  hidden_changed: boolean
  before_hidden: boolean | null
  after_hidden: boolean | null
}

export interface AuditPresetChange {
  change_type: string
  label: string
  before_value: unknown
  after_value: unknown
}

export interface AuditLockingChange {
  change_type: string
  before_state: string | null
  after_state: string | null
}

export interface AuditLogResponse {
  entries: AuditEntry[]
  total: number
}

export async function fetchAuditLog(params?: {
  limit?: number
  offset?: number
  scope?: string
  target?: string
}): Promise<AuditLogResponse> {
  const query = new URLSearchParams()
  if (params?.limit !== undefined) query.set('limit', String(params.limit))
  if (params?.offset !== undefined) query.set('offset', String(params.offset))
  if (params?.scope) query.set('scope', params.scope)
  if (params?.target) query.set('target', params.target)
  const url = `${BASE}/config/audit${query.toString() ? `?${query}` : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to load audit log: ${res.statusText}`)
  return res.json() as Promise<AuditLogResponse>
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

// ---------------------------------------------------------------------------
// Snapshots
// ---------------------------------------------------------------------------

export interface SnapshotMeta {
  snapshot_id: string
  name: string
  created_at: string
  scope: string
  target: string
}

export async function createSnapshot(
  scope: string,
  target: string,
  name: string
): Promise<SnapshotMeta> {
  const res = await fetch(`${BASE}/config/snapshots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope, target, name }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
  return res.json() as Promise<SnapshotMeta>
}

export async function listSnapshots(scope: string, target: string): Promise<SnapshotMeta[]> {
  const params = new URLSearchParams({ scope, target })
  const res = await fetch(`${BASE}/config/snapshots?${params}`)
  if (!res.ok) throw new Error(`Failed to list snapshots: ${res.statusText}`)
  return res.json() as Promise<SnapshotMeta[]>
}

export async function restoreSnapshot(
  scope: string,
  target: string,
  snapshotId: string
): Promise<SnapshotMeta> {
  const res = await fetch(`${BASE}/config/snapshots/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope, target, snapshot_id: snapshotId }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
  return res.json() as Promise<SnapshotMeta>
}

export async function deleteSnapshot(
  scope: string,
  target: string,
  snapshotId: string
): Promise<void> {
  const params = new URLSearchParams({ scope, target })
  const res = await fetch(
    `${BASE}/config/snapshots/${encodeURIComponent(snapshotId)}?${params}`,
    { method: 'DELETE' }
  )
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
}
