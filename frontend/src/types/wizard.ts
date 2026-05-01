export type FieldType = 'text' | 'textarea' | 'select' | 'multi_select' | 'multiselect' | 'checkbox' | 'boolean' | 'agent_list' | 'repeatable_group' | 'number'

export type OutputFormat = 'text' | 'markdown' | 'markdown_frontmatter' | 'verbatim'

export type PresetMode = 'append' | 'replace' | 'merge_json'

export interface Preset {
  label: string
  description?: string
  value: unknown
  mode?: PresetMode
  tags?: string[]
}

export interface PresetAssignment {
  id: string
  preset_id: string
  display_order: number
  assignment_mode: 'suggested' | 'defaulted' | 'locked' | 'hidden_applied'
  is_editable: boolean
  is_visible: boolean
  is_default: boolean
  preset: Preset
}

export interface PreviewTarget {
  target: string
  label: string
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
  preset_files?: string[]
  tag_source?: boolean
  validation?: Record<string, unknown>
  render?: boolean
  fields?: WizardField[]
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
  supported_surfaces?: string[]
  hidden?: boolean
}

export interface WizardConfigSummary {
  id: string
  title: string
  description: string
  target: string
}

export interface WizardConfig extends WizardConfigSummary {
  schema_version?: string
  target_version_constraints?: Record<string, string>
  output_preview_targets?: PreviewTarget[]
  steps: WizardStep[]
}

/** shape written to the answers store: stepId -> fieldId -> value */
export type WizardAnswers = Record<string, Record<string, unknown>>

// Editable Config Types
export type Editability = 'free' | 'locked' | 'suggested' | 'defaulted'

export interface EditableField extends WizardField {
  editability: Editability
  is_locked: boolean
  is_default: boolean
  override_source?: string
  source_file?: string
  current_value?: unknown
  current_value_source?: string
  preset_assignments?: PresetAssignment[]
  lock_reason?: string
}

export interface EditableStepData {
  id: string
  title: string
  description?: string
  fields: EditableField[]
}

export interface SourceTracking {
  total_fields: number
  by_source: Record<string, number>
  by_editability: Record<Editability, number>
  locked_fields: number
  default_fields: number
  overridden_fields: number
}

export interface EditableStep {
  step: EditableStepData
  source_tracking: SourceTracking
}
