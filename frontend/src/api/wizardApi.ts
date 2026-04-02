import type { WizardAnswers, WizardConfig, WizardConfigSummary } from '@/types/wizard'

const BASE = 'http://localhost:8000'

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
