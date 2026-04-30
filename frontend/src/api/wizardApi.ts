import type { WizardAnswers, WizardConfig, WizardConfigSummary, EditableStep, Preset, PresetAssignment } from '@/types/wizard'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const DEFAULT_TIMEOUT_MS = 30_000

/** Fetch with an AbortController timeout. */
async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs}ms`)
    }
    throw err
  } finally {
    clearTimeout(id)
  }
}

/** Throw with error detail parsed from the JSON response body. */
async function throwIfNotOk(res: Response, context: string): Promise<void> {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail
    throw new Error(detail ? `${context}: ${detail}` : `${context}: ${res.statusText}`)
  }
}

export type { EditableStep }

export async function fetchConfigs(): Promise<WizardConfigSummary[]> {
  const res = await fetchWithTimeout(`${BASE}/api/wizard/configs`)
  await throwIfNotOk(res, 'Failed to load configs')
  return res.json() as Promise<WizardConfigSummary[]>
}

export async function fetchWizardConfig(id: string, language?: string): Promise<WizardConfig> {
  const params = new URLSearchParams()
  if (language) params.append('language', language)
  const query = params.toString()
  const url = query 
    ? `${BASE}/api/wizard/config/${encodeURIComponent(id)}?${query}`
    : `${BASE}/api/wizard/config/${encodeURIComponent(id)}`
  const res = await fetchWithTimeout(url)
  await throwIfNotOk(res, `Failed to load config '${id}'`)
  return res.json() as Promise<WizardConfig>
}

export async function generateFiles(configId: string, answers: WizardAnswers): Promise<void> {
  const res = await fetchWithTimeout(`${BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id: configId, answers }),
  })
  await throwIfNotOk(res, 'Generation failed')

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
  const res = await fetchWithTimeout(`${BASE}/api/generate/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id: configId, answers }),
  })
  await throwIfNotOk(res, 'Preview failed')
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
  const res = await fetchWithTimeout(`${BASE}/config/tools`)
  await throwIfNotOk(res, 'Failed to load tools')
  return res.json() as Promise<ToolOption[]>
}

export async function fetchAvailableLanguages(): Promise<LanguageOption[]> {
  const res = await fetchWithTimeout(`${BASE}/config/languages`)
  await throwIfNotOk(res, 'Failed to load languages')
  return res.json() as Promise<LanguageOption[]>
}

export interface CreateLanguagePayload {
  title: string
  description?: string
  based_on?: string
  /** Optional tag remapping applied to all presets: { oldTag: newTag } */
  tag_remap?: Record<string, string>
}

export async function createLanguageConfig(payload: CreateLanguagePayload): Promise<LanguageOption> {
  const res = await fetchWithTimeout(`${BASE}/config/languages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await throwIfNotOk(res, 'Failed to create language')
  const data = await res.json() as { language_id: string; metadata?: { title?: string; description?: string } }
  return {
    id: data.language_id,
    title: data.metadata?.title ?? data.language_id,
    description: data.metadata?.description ?? '',
  }
}

export async function fetchLanguageTags(languageId: string): Promise<string[]> {
  const res = await fetchWithTimeout(`${BASE}/config/languages/${encodeURIComponent(languageId)}/tags`)
  await throwIfNotOk(res, 'Failed to load tags')
  return res.json() as Promise<string[]>
}

export async function fetchAvailableSteps(tool: string, language: string): Promise<StepOption[]> {
  const res = await fetchWithTimeout(`${BASE}/config/steps?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}`)
  await throwIfNotOk(res, 'Failed to load steps')
  return res.json() as Promise<StepOption[]>
}

export async function fetchEditableConfig(tool: string, language: string, stepId: string): Promise<EditableStep> {
  const res = await fetchWithTimeout(`${BASE}/config/edit?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}&step_id=${encodeURIComponent(stepId)}`)
  await throwIfNotOk(res, 'Failed to load editable config')
  return res.json() as Promise<EditableStep>
}

export async function updateFieldMetadata(
  scope: string,
  target: string,
  stepId: string,
  fieldId: string,
  changes: Record<string, unknown>,
  tool: string,
  language: string
): Promise<EditableStep> {
  const res = await fetchWithTimeout(`${BASE}/config/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope,
      target,
      tool,
      language,
      step_id: stepId,
      field_id: fieldId,
      changes,
    }),
  })
  await throwIfNotOk(res, 'Failed to update field metadata')
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

  const res = await fetchWithTimeout(`${BASE}/config/update`, {
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
  await throwIfNotOk(res, 'Failed to save field value')
  return res.json() as Promise<EditableStep>
}

export async function resetFieldToBase(
  scope: string,
  target: string,
  stepId: string,
  fieldId: string,
  tool: string,
  language: string,
  overrideType: 'metadata' | 'structure' = 'metadata'
): Promise<EditableStep> {
  const res = await fetchWithTimeout(`${BASE}/config/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope,
      target,
      tool,
      language,
      step_id: stepId,
      field_id: fieldId,
      override_type: overrideType,
    }),
  })
  await throwIfNotOk(res, 'Failed to reset field to base')
  return res.json() as Promise<EditableStep>
}

export async function fetchAvailablePresets(tool: string, language: string): Promise<{
  shared: Preset[]
  language: Preset[]
  tool: Preset[]
}> {
  const res = await fetchWithTimeout(`${BASE}/api/wizard/presets?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}`)
  await throwIfNotOk(res, 'Failed to load presets')
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
  const res = await fetchWithTimeout(`${BASE}/api/wizard/field-presets?tool=${encodeURIComponent(tool)}&language=${encodeURIComponent(language)}&field_id=${encodeURIComponent(fieldId)}`)
  await throwIfNotOk(res, 'Failed to load field preset assignments')
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
  const res = await fetchWithTimeout(url)
  await throwIfNotOk(res, 'Failed to load audit log')
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
  const res = await fetchWithTimeout(`${BASE}/api/wizard/field-presets`, {
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
  await throwIfNotOk(res, 'Failed to assign preset')
  return res.json() as Promise<PresetAssignment>
}

export async function updatePresetAssignment(
  assignmentId: string,
  changes: Partial<PresetAssignment>
): Promise<PresetAssignment> {
  const res = await fetchWithTimeout(`${BASE}/api/wizard/field-presets/${encodeURIComponent(assignmentId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
  await throwIfNotOk(res, 'Failed to update preset assignment')
  return res.json() as Promise<PresetAssignment>
}

export async function removePresetFromField(assignmentId: string): Promise<void> {
  const res = await fetchWithTimeout(`${BASE}/api/wizard/field-presets/${encodeURIComponent(assignmentId)}`, {
    method: 'DELETE',
  })
  await throwIfNotOk(res, 'Failed to remove preset assignment')
}

export async function reorderPresetAssignments(
  tool: string,
  language: string,
  fieldId: string,
  assignmentIds: string[]
): Promise<void> {
  const res = await fetchWithTimeout(`${BASE}/api/wizard/field-presets/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool,
      language,
      field_id: fieldId,
      assignment_ids: assignmentIds,
    }),
  })
  await throwIfNotOk(res, 'Failed to reorder preset assignments')
}


// ---------------------------------------------------------------------------
// Coverage matrix
// ---------------------------------------------------------------------------

export type CoverageStatus = 'full' | 'partial' | 'none'

export interface CoverageCell {
  status: CoverageStatus
  field_count: number
  fields: string[]
}

export interface CoverageMatrix {
  tools: Array<{ id: string; title: string }>
  languages: Array<{ id: string; title: string }>
  matrix: Record<string, Record<string, CoverageCell>>
}

export async function fetchCoverageMatrix(): Promise<CoverageMatrix> {
  const res = await fetchWithTimeout(`${BASE}/config/coverage`)
  await throwIfNotOk(res, 'Failed to load coverage matrix')
  return res.json() as Promise<CoverageMatrix>
}


// ---------------------------------------------------------------------------
// Version history
// ---------------------------------------------------------------------------

export interface VersionMeta {
  version: number
  timestamp: string
  actor: string
  summary: string
  scope: string
  target: string
}

export interface VersionEnvelope extends VersionMeta {
  data: Record<string, unknown>
}

export interface VersionDiff {
  v1: number
  v2: number
  scope: string
  target: string
  diff: Record<string, unknown>
}

export async function fetchVersionHistory(scope: string, target: string): Promise<VersionMeta[]> {
  const params = new URLSearchParams({ scope, target })
  const res = await fetchWithTimeout(`${BASE}/config/history?${params}`)
  await throwIfNotOk(res, 'Failed to load version history')
  return res.json() as Promise<VersionMeta[]>
}

export async function fetchVersion(scope: string, target: string, version: number): Promise<VersionEnvelope> {
  const params = new URLSearchParams({ scope, target })
  const res = await fetchWithTimeout(`${BASE}/config/history/${version}?${params}`)
  await throwIfNotOk(res, 'Failed to load version')
  return res.json() as Promise<VersionEnvelope>
}

export async function fetchVersionDiff(
  scope: string,
  target: string,
  v1: number,
  v2: number,
): Promise<VersionDiff> {
  const params = new URLSearchParams({ scope, target, v1: String(v1), v2: String(v2) })
  const res = await fetchWithTimeout(`${BASE}/config/history/diff?${params}`)
  await throwIfNotOk(res, 'Failed to load version diff')
  return res.json() as Promise<VersionDiff>
}
