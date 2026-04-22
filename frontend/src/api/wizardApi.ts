import type { WizardAnswers, WizardConfig, WizardConfigSummary, EditableStep } from '@/types/wizard'

const BASE = 'http://localhost:8000'

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
