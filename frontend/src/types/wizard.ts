export type FieldType = 'text' | 'textarea' | 'select' | 'multi_select' | 'checkbox' | 'agent_list'

export type OutputFormat = 'text' | 'markdown' | 'markdown_frontmatter' | 'verbatim'

export type PresetMode = 'append' | 'replace' | 'merge_json'

export interface Preset {
  label: string
  description?: string
  value: unknown
  mode?: PresetMode
}

export interface AgentEntry {
  name: string
  description?: string
  tools?: string[]
  model?: string
  system_prompt?: string
}

export interface AgentFieldConfig {
  output_dir: string
  file_suffix?: string
  available_tools?: string[]
  available_models?: string[]
  default_model?: string
}

export interface FieldOption {
  value: string
  label: string
  description?: string
}

export interface WizardField {
  id: string
  type: FieldType
  label: string
  description?: string
  placeholder?: string
  required: boolean
  options?: FieldOption[]
  default?: unknown
  rows?: number
  frontmatter?: boolean
  frontmatter_key?: string | null
  screen_hint?: string
  presets?: Preset[]
  locked_value?: string
  agent_config?: AgentFieldConfig
}

export interface WizardStep {
  id: string
  title: string
  description?: string
  hint?: string
  fields: WizardField[]
  output_file: string
  output_format?: OutputFormat
}

export interface WizardConfigSummary {
  id: string
  title: string
  description: string
  target: string
}

export interface WizardConfig extends WizardConfigSummary {
  steps: WizardStep[]
}

/** shape written to the answers store: stepId -> fieldId -> value */
export type WizardAnswers = Record<string, Record<string, unknown>>
