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

// Phase 5A — Visibility rules
export type RuleOperator = 'equals' | 'not_equals' | 'in' | 'not_in' | 'is_empty' | 'is_not_empty'
export type RuleAction = 'show' | 'hide'
export type RuleTargetType = 'step' | 'field'

export interface VisibilityRule {
  id: number
  target_type: RuleTargetType
  target_step_key: string
  target_field_path?: string
  depends_on_field_path: string
  operator: RuleOperator
  value: unknown
  action: RuleAction
  priority: number
}

export interface VisibilityResult {
  steps: Record<string, boolean>
  fields: Record<string, boolean>
  rules_evaluated: number
}

// Phase 5B — Wizard flows
export interface WizardFlowStep {
  id: number
  step_key: string
  position: number
  is_enabled: boolean
  custom_title?: string | null
  custom_description?: string | null
}

export interface WizardFlow {
  id: number
  name: string
  description: string
  owner_actor: string
  source_schema_id: number | null
  source_tool_id: number | null
  is_default: boolean
  status: string
  steps?: WizardFlowStep[]
  created_at: string | null
  updated_at: string | null
}
