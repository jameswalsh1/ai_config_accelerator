# JSON Configuration Model

> Internal reference document for the AI Configuration Wizard.  
> Scope: current JSON-based configuration system as of May 2026.  
> Purpose: pre-migration baseline for the JSON → database epic.

---

## Overview

The wizard generates AI tool configuration files (Claude, GitHub Copilot, Cursor) from a layered JSON configuration system. JSON files on disk are the **canonical source of truth**. The system is composed of:

- A single **canonical schema** (`schema.json`) that defines all possible steps and fields for every tool.
- **Tool override files** that select which steps are visible and supply tool-specific metadata.
- **Language override files** that inject language-specific presets and defaults.
- **Combo override files** (optional) that apply the highest-priority overrides for a specific tool + language combination.
- A **version history** store that archives every saved override revision.

---

## Directory Structure

All configuration data lives under `backend/app/data/wizard_configs/`:

```
wizard_configs/
├── schema.json                     # Canonical schema — defines every step and field
├── override.schema.json            # JSON Schema for validating override files
├── audit.jsonl                     # Append-only audit log of all saves
├── demo.json                       # Demo configuration snapshot
│
├── tools/                          # Tool-specific override files (one per tool)
│   ├── claude.json
│   ├── copilot.json
│   └── cursor.json
│
├── languages/                      # Language-specific override files (one per language)
│   ├── angular.json
│   ├── dotnet.json
│   ├── java.json
│   ├── python.json
│   ├── react-typescript.json
│   └── typescript.json
│
├── overrides/                      # Tool+language combo overrides (currently empty)
│   └── (empty — e.g. claude+python.json would live here)
│
├── shared/
│   └── preset_files/               # Reusable preset arrays loaded by reference
│       └── llm.json
│
└── history/                        # Immutable version history of saved overrides
    └── language/
        └── {language_id}/
            ├── v001.json
            ├── v002.json
            └── ...
```

**Assumptions made about file names and paths:**

- Tool files are named exactly `{tool_id}.json` — the stem is used as the `config.id`.
- Language files are named exactly `{language_id}.json` — matched by the `language_id` field value.
- Combo files follow the pattern `{tool_id}+{language_id}.json`.
- `schema.json` must always exist at the root of `wizard_configs/`. Its absence raises `FileNotFoundError`.
- Tool files are required for a tool to appear in the system. A missing tool file means `get_config()` returns `None`.
- Language files and combo files are optional; the loader silently skips missing files.
- `shared/preset_files/` paths in `preset_files` arrays are relative to `wizard_configs/`.

---

## schema.json — Canonical Schema

`schema.json` defines every step and every field for all three tools combined. It is loaded first on every composition. Fields and steps that are irrelevant to a particular tool are suppressed via `step_overrides` in the tool file.

### Top-level structure

```json
{
  "schema_version": "2.0",
  "description": "...",
  "steps": [ ... ]
}
```

### Step object

```json
{
  "id": "claude_md",
  "title": "Claude Code Instructions (CLAUDE.md)",
  "description": "...",
  "hint": "...",
  "output_file": "CLAUDE.md",
  "output_format": "markdown",
  "supported_surfaces": ["chat"],
  "hidden": false,
  "fields": [ ... ]
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique step identifier. Used to address the step in overrides (`step_id`). |
| `title` | string | Display label shown in the wizard UI. |
| `description` | string | Longer explanation of what this step configures. |
| `hint` | string | Contextual hint displayed alongside the step. |
| `output_file` | string | Relative path of the generated file (e.g. `CLAUDE.md`, `.github/copilot-instructions.md`). Empty string means no single output file. |
| `output_format` | enum | Rendering mode: `text`, `markdown`, `markdown_frontmatter`, `json`. Controls how `file_generator.py` renders the step. |
| `supported_surfaces` | string[] | Optional list of tool surfaces this step targets. |
| `hidden` | boolean | If `true`, the step is excluded from the wizard flow. Normally set by tool `step_overrides`. |
| `fields` | array | Ordered list of field objects (see below). |

### Field object

```json
{
  "id": "tech_stack",
  "type": "textarea",
  "label": "Technology Stack",
  "description": "...",
  "placeholder": "...",
  "required": false,
  "default": null,
  "editability": "free",
  "locked_value": "...",
  "render": true,
  "hidden": false,
  "presets": [],
  "preset_files": ["shared/preset_files/llm.json"],
  "options": null,
  "screen_hint": "...",
  "frontmatter": false,
  "frontmatter_key": null,
  "tag_source": false,
  "validation": null,
  "fields": null,
  "agent_config": null,
  "override_source": null
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique field identifier within the step. Used as the second segment of `field_id` paths (e.g. `claude_md.tech_stack`). |
| `type` | enum | Field UI type. Values: `text`, `textarea`, `select`, `multi_select`, `toggle`, `repeatable_group`, `agent_list`, `code`. |
| `label` | string | Display label. |
| `description` | string | Secondary explanation shown below the label. |
| `placeholder` | string | Input placeholder text. |
| `required` | boolean | If `true`, the wizard will not proceed without a value. |
| `default` | any | Default value pre-populated for the field. Overridable via `metadata_overrides`. |
| `editability` | enum | Controls user interaction. See [Editability States](#editability-states). |
| `locked_value` | string | Read-only content always prepended to generated output; never overridden by user input. |
| `render` | boolean | If `false`, the field contributes metadata but is not emitted in the generated file. |
| `hidden` | boolean | If `true`, the field is not shown in the UI. |
| `options` | array | For `select` and `multi_select` fields — list of `{ value, label, description }` objects. |
| `presets` | array | Quick-fill preset chips shown below the field. See [Preset object](#preset-object). |
| `preset_files` | string[] | Paths (relative to `wizard_configs/`) of external JSON files containing additional presets. Resolved before the config is returned. |
| `screen_hint` | string | Verbose per-field help text displayed when the field is active. |
| `frontmatter` | boolean | For `markdown_frontmatter` steps — emit this field in the YAML front matter block. |
| `frontmatter_key` | string | YAML key name; defaults to `field.id` when `frontmatter` is `true`. |
| `tag_source` | boolean | Values from this field are used as active tag filters for preset visibility. |
| `validation` | object | Optional field-level validation rules. |
| `fields` | array | Nested field definitions — used by `repeatable_group` and `agent_list` types. |
| `agent_config` | object | Extra metadata for `agent_list` fields: `output_dir`, `file_suffix`, `available_tools`, `available_models`, `default_model`. |
| `override_source` | string | **Runtime metadata only.** Injected by the loader to track which layer last modified this field. Not present in source files. |

### Editability States

| Value | Meaning |
|---|---|
| `free` | User can edit freely. This is the default. |
| `locked` | Field is read-only; the value was set by an override and cannot be changed by the user. |
| `suggested` | The value is a recommendation from an override; user can accept or change it. |
| `defaulted` | Field is pre-filled by the schema default; user can edit it. |

### Preset object

```json
{
  "label": "FastAPI",
  "description": "Modern async Python web framework",
  "value": "FastAPI, Pydantic v2, uvicorn, SQLAlchemy 2.x",
  "mode": "overwrite",
  "tags": ["python"]
}
```

| Field | Type | Description |
|---|---|---|
| `label` | string | Display name shown on the chip. |
| `description` | string | Optional tooltip/subtitle. |
| `value` | any | Value to insert when preset is selected. |
| `mode` | enum | How the value is applied: `append` (add to existing), `overwrite` (replace), `replace`. |
| `tags` | string[] | If present, preset is only shown when one of these tags matches the active language selection. |

---

## Preset File Migration Considerations

The current system supports inline presets and external preset files via `preset_files`.

Example:

```json
"preset_files": ["shared/preset_files/llm.json"]
```

The loader resolves these paths relative to `wizard_configs/` and expands them inline before returning the composed config.

For the first database migration, the system may continue to support preset files to preserve behaviour. However, the long-term database-backed model should consider moving reusable presets into first-class database records.

Possible future model:

```
config_preset
- id
- field_id
- label
- description
- value_json
- mode
- tags_json
- source_layer
```

Open decision: Are shared presets part of the canonical database model, or do they remain file-based external resources?

Recommended long-term answer: Move shared presets into the database once the core schema, override, and resolver migration is complete. Keep JSON import/export so presets remain reviewable.

**Migration rule:** Preset expansion behaviour must remain unchanged until a dedicated preset migration is implemented.

---

## Output Rendering Model

Each step currently has output rendering metadata such as:

```json
{
  "output_file": "CLAUDE.md",
  "output_format": "markdown"
}
```

This works for simple cases where one step maps to one generated file. Some current and future cases are more complex:

- Cursor rule files may produce multiple `.mdc` files.
- Claude agents may produce multiple agent files.
- Claude skills may produce multiple skill files.
- Copilot prompt files may produce multiple prompt files.
- Repeatable groups may produce one file per item.

The initial database migration should preserve the current `output_file` and `output_format` fields exactly. Longer term, output rendering may need a first-class model such as:

```
config_output_target
- id
- step_id
- output_path_template
- output_format
- renderer_key
- is_repeatable
```

**Migration rule:** Do not change generated file output behaviour during the database migration. The same selected config should produce the same files before and after migration.

---

## Schema Ownership and Tool-Specific Steps

The current implementation uses a single global `schema.json` that defines all possible steps and fields for every supported AI tool. This is currently an implementation convenience and should be preserved during the first migration phase to avoid changing behaviour.

However, some steps are effectively tool-specific:

- Claude-specific examples: `claude_md`, `claude_settings`, `mcp_config`, `agent_definitions`, `skill_definitions`, `hooks`, `verification_policy`
- GitHub Copilot-specific examples: `repo_instructions`, `path_instructions`, `prompt_files`, `custom_agents`, `repo_settings`
- Cursor-specific examples: `rule_files`, `cursor_ignore`, `cursor_indexing_content`, `cursor_indexing_strategy`, `cursor_settings`, `ignore_verification`

In the database-backed model, the first implementation should preserve the current global schema behaviour. Longer term, the database model should explicitly support step ownership or applicability, for example:

```
config_step.scope   = global | tool_specific
config_step.tool_id = nullable
```

This would allow the system to distinguish genuinely shared steps from tool-specific steps without relying entirely on tool override files to hide irrelevant steps.

**Migration rule:** `schema.json` remains the canonical definition of every known step and field until database parity is proven.

---

## Tool Override Files (`tools/{tool_id}.json`)

Each tool file configures which steps are active for that tool and provides tool-level metadata. It does **not** redefine steps from scratch — it references existing step IDs.

### Top-level structure

```json
{
  "tool_id": "claude",
  "tool_metadata": {
    "title": "Claude Code Configuration",
    "description": "...",
    "target": "claude",
    "schema_version": "1.0",
    "target_version_constraints": { "claude_code": ">=1.0.0" },
    "output_preview_targets": [ { "target": "claude_md", "label": "CLAUDE.md" } ],
    "file_classification": { ... }
  },
  "version": "1.0",
  "applies_to": { "tools": ["claude"] },
  "metadata_overrides": [],
  "field_overrides": [],
  "step_overrides": [
    { "step_id": "cursor_ignore", "hidden": true },
    { "step_id": "rule_files", "hidden": true }
  ]
}
```

| Field | Description |
|---|---|
| `tool_id` | Must match the file stem (e.g. `claude`). Used to identify the tool. |
| `tool_metadata` | Merged into the composed config at the top level: sets `title`, `description`, `target`, and additional display metadata. |
| `version` | Override schema version string (`"1.0"`). |
| `applies_to.tools` | Restricts this override to the named tools. Validated at load time. |
| `metadata_overrides` | Field-level metadata patches (default, editability, etc.). See [Override resolution](#override-resolution). |
| `field_overrides` | Structural patches (options, presets). See [Override resolution](#override-resolution). |
| `step_overrides` | Step-level patches. Primarily used to hide irrelevant steps with `"hidden": true`. |

### Example: Claude tool file highlights

Claude shows: `language_selection`, `claude_md`, `claude_settings`, `mcp_config`, `agent_definitions`, `skill_definitions`, `build_test_commands`, `hooks`, `verification_policy`.

Claude hides all Copilot-only and Cursor-only steps via `step_overrides`.

### Example: Copilot tool file highlights

Copilot shows: `language_selection`, `repo_instructions`, `path_instructions`, `agent_skills`, `prompt_files`, `agent_instruction_files`, `custom_agents`, `repo_settings`.

### Example: Cursor tool file highlights

Cursor shows: `language_selection`, `rule_files`, `agents_heading`, `agents_guidance`, `agent_instruction_files`, `agent_skills`, `cursor_ignore`, `cursor_indexing_content`, `cursor_indexing_strategy`, `cursor_settings`, `ignore_verification`.

---

## Step Visibility Model

The current system starts with all steps from `schema.json` and then uses `step_overrides` in each tool file to hide steps that are not relevant to the selected tool.

Current model:

```
Load all steps
→ hide irrelevant tool steps
→ return visible wizard flow
```

This means `hidden: true` is currently used as the main tool-specific step selection mechanism.

This behaviour must be preserved during the first database migration. However, in the long-term database-backed model, step selection may be cleaner if templates explicitly include only the steps that apply to the tool/language combination.

Future model:

```
config_step
→ template_step
→ ordered visible wizard flow
```

In that model, `hidden` should still exist for conditional UI visibility, but not be the primary way of defining which steps belong to a tool.

**Migration rule:** The database-backed resolver must initially reproduce the current hidden-step behaviour exactly.

---

## Language Override Files (`languages/{language_id}.json`)

Language files inject language-specific presets and metadata overrides into the composed config. They use the same `metadata_overrides`, `field_overrides`, and `step_overrides` keys as tool files.

### Top-level structure

```json
{
  "language_id": "python",
  "version": "1.0",
  "metadata": {
    "title": "Python",
    "description": "Python 3.13+ — FastAPI, Django, or data science"
  },
  "applies_to": { "languages": ["python"] },
  "metadata_overrides": [],
  "field_overrides": [ ... ],
  "step_overrides": []
}
```

| Field | Description |
|---|---|
| `language_id` | Must match the file stem (e.g. `python`). |
| `metadata.title` / `metadata.description` | Display metadata for the language selection UI. |
| `applies_to.languages` | Restricts this override to the named languages. |
| `field_overrides` | Typically adds language-specific presets to shared fields like `claude_md.tech_stack` and `claude_md.coding_conventions`. |

Supported language IDs: `angular`, `dotnet`, `java`, `python`, `react-typescript`, `typescript`.

---

## Combo Override Files (`overrides/{tool_id}+{language_id}.json`)

These files apply the highest-priority overrides for a specific tool + language pair. They have the same structure as language override files. The directory is currently empty — no combo overrides are defined.

**Naming assumption:** the file must be named exactly `{tool_id}+{language_id}.json` (e.g. `claude+python.json`). The `+` character is literal.

---

## Override Resolution — Composition Order

The loader (`config_loader_composable.py → load_composable_config`) applies overrides in this fixed order:

```
1. schema.json           → canonical base (all steps + fields)
2. tools/{tool_id}.json  → tool overrides (step visibility, tool metadata)
3. languages/{language_id}.json → language overrides (presets, defaults)
4. overrides/{tool_id}+{language_id}.json → combo overrides (highest priority)
5. preset_files resolved → all preset_files references expanded inline
```

Each layer is applied by mutating a deep copy of the config, so a failed layer does not corrupt earlier state.

### `metadata_overrides` resolution

Each entry targets a field by `field_id` path (`step_id.field_id` or `step_id.field_id.nested_id`) and patches these properties:

| Property | Effect |
|---|---|
| `default` | Replaces the field's default value. |
| `editability` | Replaces the field's editability state. |
| `required` | Replaces the required flag. |
| `hidden` | Hides or unhides the field. |
| `lock_reason` | Sets an explanatory string shown when the field is locked. |

### `field_overrides` resolution

Each entry targets a field by `field_id` and patches structural content:

| Property | Effect |
|---|---|
| `replace_options_with` | Replaces all select options. |
| `merge_options` | Appends new options to the existing list. |
| `replace_presets_with` | Replaces all presets. |
| `merge_presets` | Merges new presets using `merge_mode`. |
| `preset_files_to_add` | Appends paths to the field's `preset_files` list. |
| `merge_mode` | Controls preset merging: `append` (default), `merge_by_label` (update by label), `replace`. |

### `step_overrides` resolution

Each entry targets a step by `step_id` and patches:

| Property | Effect |
|---|---|
| `hidden` | Hides or shows the step. |
| `title_override` | Replaces the step title. |
| `description_override` | Replaces the step description. |
| `hint_override` | Replaces the step hint. |

### `override_source` tracking

Every field that is modified by an override layer receives an `override_source` string identifying the layer, e.g.:

- `"tool:claude"` — set by the Claude tool file
- `"language:python"` — set by the Python language file
- `"override:claude+python"` — set by a combo override

This field is injected at runtime and is **not** present in source JSON files.

---

## Source Attribution Requirements

The current resolver injects `override_source` metadata into fields that are modified by an override layer. This is useful runtime metadata and should be preserved in the database-backed resolver.

The database-backed resolver should be able to explain where a value came from:

```
schema
tool:claude
language:python
override:claude+python
user_revision:{revision_id}
```

This attribution is useful for both the regular wizard and the config editor. It allows the UI to show explanations such as:

- _This value comes from the Python language defaults._
- _This field was locked by the Claude tool configuration._
- _This preset was added by the Python language override._

**Migration rule:** Resolved config output from the database must preserve source attribution for overridden fields, presets, options, and step visibility changes where practical.

---

## Resolved Config Example

**Request:**

```
tool     = claude
language = python
```

**Resolution flow:**

```
1. Load schema.json
2. Apply tools/claude.json
3. Apply languages/python.json
4. Apply overrides/claude+python.json if present
5. Resolve preset_files references
6. Return final composed wizard config
```

**Example field before language override:**

```json
{
  "field_id": "claude_md.tech_stack",
  "default": null,
  "presets": []
}
```

**Example after applying `languages/python.json`:**

```json
{
  "field_id": "claude_md.tech_stack",
  "default": null,
  "presets": [
    {
      "label": "FastAPI",
      "value": "FastAPI, Pydantic v2, uvicorn, SQLAlchemy 2.x",
      "mode": "overwrite",
      "tags": ["python"]
    },
    {
      "label": "Django",
      "value": "Django 5.x, Django REST Framework, Celery",
      "mode": "overwrite",
      "tags": ["python"]
    }
  ],
  "override_source": "language:python"
}
```

This example should be used as a baseline for database parity tests.

---

## Override Categories and Database Mapping

The current JSON model separates field-level overrides into two categories:

- `metadata_overrides`: default values, editability, required state, hidden state, lock reason.
- `field_overrides`: options, presets, preset file references, and merge behaviour.

This split is useful in JSON because it separates simple metadata patches from structural field content patches. In the database model, both categories should still be preserved conceptually, but they may be stored either as separate tables or as a unified override table with a patch type.

Recommended migration-safe approach:

```
config_field_metadata_override
config_field_content_override
config_step_override
```

Alternative generic approach:

```
config_override
- id
- layer_type
- layer_key
- target_type
- target_path
- patch_type
- patch_json
```

The first migration should prefer clarity over over-generalisation. Therefore, separate tables that map closely to the current JSON concepts are likely easier to test and safer to implement incrementally.

**Migration rule:** Do not flatten `metadata_overrides` and `field_overrides` into final resolved field values only. The database must preserve which layer supplied each override.

---

## Generated User Revisions — Version History

When a configuration override is saved (via `config_persistence.py → save_config`), the system:

1. Validates the data against the appropriate JSON schema.
2. Optionally creates a `.backup` file alongside the original (e.g. `python.json.backup`).
3. Atomically writes the new content via `tempfile → os.rename`.
4. Appends an entry to `audit.jsonl`.

Separately, `version_history.py → save_version` archives a full snapshot of the config to:

```
data/wizard_configs/history/{scope}/{target}/v{NNN}.json
```

- `scope`: `"tool"`, `"language"`, or `"override"`
- `target`: e.g. `"python"`, `"claude"`
- Version numbers are 1-based, zero-padded to 3 digits (`v001`, `v002`, …)

Each version file is a self-contained envelope:

```json
{
  "version": 3,
  "timestamp": "2026-04-30T14:00:00+00:00",
  "actor": "system",
  "summary": "step 'claude_md': 1 field(s) modified",
  "data": { ... full config content ... }
}
```

Version numbers are derived from filenames — no manifest file is required. There is no explicit locking beyond POSIX `rename` atomicity.

---

## Version History Migration Considerations

The current history model stores immutable snapshots on disk:

```
history/{scope}/{target}/v{NNN}.json
```

The next version number is derived from filenames rather than a manifest or database sequence.

For the first database migration, existing JSON history files should be treated as a read-only legacy archive unless there is a specific business requirement to import them.

Recommended approach:

- Keep existing history files on disk.
- Start database-backed audit/version history from the migration date.
- Do not attempt to import every old `v001`/`v002`/`v003` snapshot during the first migration.

A future migration can import historical snapshots if required.

Potential database model:

```
config_version
- id
- scope
- target_key
- version_number
- actor
- summary
- data_json
- created_at
```

**Migration rule:** Do not block the database migration on importing historical JSON version files.

---

## User Revisions vs Shared Templates

The phrase "user-generated revision" can mean two different things and should be modelled carefully.

### Personal saved config

A regular user creates a saved configuration that they can reuse later.

Example: James creates "Claude Python FastAPI baseline" and can reuse it later for another project.

This should be modelled as a user-owned revision.

Possible table:

```
user_config_revision
- id
- user_id
- source_template_id
- tool_id
- language_id
- revision_number
- name
- status
- created_at
- updated_at
```

### Shared promoted template

A user-generated revision may later be submitted, reviewed, approved, and promoted into a shared template available to other users.

Example: A user creates a strong Cursor Java configuration, approved personnel review it, and it becomes a shared template for all Java users.

This should not be treated as the same object as a personal revision. It should go through a draft/approval workflow before becoming a shared template.

Recommended distinction:

```
user_config_revision  = personal/user-owned saved config
config_template       = approved shared template
template_candidate    = user revision submitted for approval
```

**Migration rule:** Do not make all user revisions globally available by default. Promotion to shared template should be explicit and approved.

---

## Field Addressing Convention

Fields are addressed using dot-separated paths. The path structure is:

```
{step_id}.{field_id}
{step_id}.{field_id}.{nested_field_id}
```

Examples:
- `claude_md.tech_stack` — the `tech_stack` field inside the `claude_md` step
- `rule_files.rules.rule_file_name` — a nested field inside a repeatable group

The loader function `_get_field_by_id` splits the path on the first `.` to get the step, then recurses into nested `fields` arrays for any remaining path segments.

---

## Example Configurations

### Claude — tool file excerpt (`tools/claude.json`)

```json
{
  "tool_id": "claude",
  "tool_metadata": {
    "title": "Claude Code Configuration",
    "description": "Generate CLAUDE.md instructions, project settings, and MCP configuration for Claude Code.",
    "target": "claude",
    "schema_version": "1.0"
  },
  "version": "1.0",
  "applies_to": { "tools": ["claude"] },
  "metadata_overrides": [],
  "field_overrides": [],
  "step_overrides": [
    { "step_id": "cursor_ignore", "hidden": true },
    { "step_id": "rule_files", "hidden": true },
    { "step_id": "repo_instructions", "hidden": true }
  ]
}
```

### GitHub Copilot — tool file excerpt (`tools/copilot.json`)

```json
{
  "tool_id": "copilot",
  "tool_metadata": {
    "title": "GitHub Copilot Configuration",
    "description": "Generate repository-wide custom instructions, path-specific instructions, agent skills, prompt files, and custom agents for GitHub Copilot.",
    "target": "copilot",
    "schema_version": "1.0"
  },
  "version": "1.0",
  "applies_to": { "tools": ["copilot"] },
  "metadata_overrides": [],
  "field_overrides": [],
  "step_overrides": [
    { "step_id": "claude_md", "hidden": true },
    { "step_id": "rule_files", "hidden": true },
    { "step_id": "mcp_config", "hidden": true }
  ]
}
```

### Cursor — tool file excerpt (`tools/cursor.json`)

```json
{
  "tool_id": "cursor",
  "tool_metadata": {
    "title": "Cursor Configuration",
    "description": "Generate rule files, ignore patterns, and indexing config for Cursor AI editor.",
    "target": "cursor",
    "schema_version": "1.0"
  },
  "version": "1.0",
  "applies_to": { "tools": ["cursor"] },
  "metadata_overrides": [],
  "field_overrides": [],
  "step_overrides": [
    { "step_id": "claude_md", "hidden": true },
    { "step_id": "repo_instructions", "hidden": true },
    { "step_id": "mcp_config", "hidden": true }
  ]
}
```

### Python — language file excerpt (`languages/python.json`)

```json
{
  "language_id": "python",
  "version": "1.0",
  "metadata": { "title": "Python", "description": "Python 3.13+ — FastAPI, Django, or data science" },
  "applies_to": { "languages": ["python"] },
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "merge_presets": [
        { "label": "FastAPI", "value": "FastAPI, Pydantic v2, uvicorn, SQLAlchemy 2.x", "mode": "overwrite", "tags": ["python"] },
        { "label": "Django", "value": "Django 5.x, Django REST Framework, Celery", "mode": "overwrite", "tags": ["python"] }
      ],
      "merge_mode": "append"
    }
  ],
  "metadata_overrides": [],
  "step_overrides": []
}
```

### Angular — language file (`languages/angular.json`)

```json
{
  "language_id": "angular",
  "version": "1.0",
  "applies_to": { "languages": ["angular"] },
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "merge_presets": [
        { "label": "Angular + TypeScript", "value": "- Frontend: Angular 18+ with TypeScript\n- Styling: Tailwind CSS or Angular Material", "mode": "append", "tags": ["angular"] }
      ],
      "merge_mode": "append"
    }
  ],
  "metadata_overrides": [],
  "step_overrides": []
}
```

---

## Key Assumptions the Current Implementation Makes

1. **File name = identifier.** The `tool_id` in a tool file must equal the JSON filename stem; there is no registry or manifest.
2. **`schema.json` is always present.** The loader raises `FileNotFoundError` if it is missing.
3. **All paths are relative to `DATA_DIR`.** `DATA_DIR` is resolved at import time as `app/data/wizard_configs/`.
4. **`preset_files` paths are relative to `DATA_DIR`, not the referencing file.** A field with `preset_files: ["shared/preset_files/llm.json"]` always resolves from `wizard_configs/shared/preset_files/llm.json`.
5. **Field addresses use `.` as a separator.** A step ID or field ID containing `.` would break the path resolution in `_get_field_by_id`.
6. **History directories are created on first write.** No pre-initialisation is needed; `save_version` creates `history/{scope}/{target}/` on demand.
7. **Version numbering is filesystem-derived.** Renaming or deleting version files will change the next assigned version number.
8. **Backup files sit alongside originals.** `python.json.backup` is written in the same directory as `python.json`; only one backup is kept per file.
9. **`applies_to` filtering is enforced at load time.** If a tool override's `applies_to.tools` list does not include the requested `tool_id`, the override is silently skipped.

---

## Behavioural Invariants for Database Migration

The following behaviour must remain unchanged during the migration from JSON to database-backed configuration:

- Field paths must remain stable.
- Existing generated files must not change for the same selected values.
- Override application order must remain: `schema → tool → language → combo → preset file expansion`.
- Combo overrides must have the highest priority.
- Preset visibility by tags must be preserved.
- Hidden steps must not appear in the regular wizard flow.
- Hidden fields must not appear in the regular wizard UI.
- Locked fields must remain read-only for regular users.
- Suggested/defaulted/free fields must remain editable according to the current semantics.
- Runtime source attribution must remain available.
- Missing language files must continue to be optional.
- Missing combo override files must continue to be optional.
- Missing required `schema.json` must remain a hard failure.
- Existing API responses should remain compatible unless a later ticket explicitly changes the API contract.
- The database-backed resolver must produce the same normalised resolved config as the JSON-backed resolver before cutover.

---

## Known Limitations of the Current JSON Model

The current JSON model works well for a small and reviewable configuration system, but has several limitations that motivate the database migration:

- There is no central manifest of available tools and languages.
- File names are used as identifiers.
- Step selection is mostly handled by hiding irrelevant global steps.
- There are no database-level constraints for field IDs or step IDs.
- Version history is derived from filesystem filenames.
- There is no transaction boundary across config save, audit append, and version save.
- Backup behaviour only preserves one `.backup` file beside the original.
- Preset files are external resources resolved at runtime.
- There is limited ability to query which templates or overrides use a given field.
- There is limited support for approval workflows.
- It is difficult to safely reorder steps across multiple tools/languages without drift.
- It is difficult to compare intended source changes against final resolved output.
- There is no first-class distinction between a personal saved user config and an approved shared template.

---

## API Surface To Document

The migration document should include the current backend API endpoints used by the config wizard and config editor before implementation begins.

**TODO:** Document current endpoints, request payloads, and response payloads for:

- Listing available tools
- Listing available languages
- Loading a composed config for tool + language
- Saving tool/language/combo overrides
- Loading version history
- Restoring a previous version
- Generating output files
- Loading generated user revisions

This is required so that the initial database migration can preserve API compatibility.

---

## Pre-Migration Implementation Questions

Before creating the database migration Jira tickets, the following implementation details must be confirmed from the current codebase.

---

### 1. Current API Surface

The backend exposes three routers, registered in `backend/app/main.py`.

#### Wizard router — `backend/app/routers/wizard.py` (prefix: `/api/wizard`)

| Method | Path | Purpose | Auth required | Mutates disk |
|---|---|---|---|---|
| GET | `/api/wizard/configs` | List all tools as summary objects | None | No |
| GET | `/api/wizard/config/resolved` | Load composed config for tool + language | None | No |
| GET | `/api/wizard/config/edit` | Load editable step slice with override metadata | None | No |
| GET | `/api/wizard/config/{config_id}` | Load tool config, optionally filtered by language | None | No |
| GET | `/api/wizard/presets` | Load categorised presets for tool + language | None | No |

All wizard router endpoints are **read-only and unauthenticated**.

#### Generate router — `backend/app/routers/generate.py` (prefix: `/api`)

| Method | Path | Purpose | Auth required | Mutates disk |
|---|---|---|---|---|
| POST | `/api/generate/preview` | Return generated file contents as JSON | None | No |
| POST | `/api/generate` | Generate and return a ZIP download | None | No |

**Note:** `POST /api/generate` does not write generated files to disk. It returns them as a `StreamingResponse` ZIP. The generated content is ephemeral — the same answers always produce the same output (deterministic).

**No endpoint currently exists for saving or loading user-generated file revisions.** Generated output is produced on demand and returned directly.

```
Status: No saved/generated user revision storage currently implemented
Migration implication: The database migration will need to decide whether user revisions should be persisted separately from override templates.
```

#### Config editor router — `backend/app/routers/config.py` (prefix: `/config`)

| Method | Path | Purpose | Handler | Auth required | Mutates disk |
|---|---|---|---|---|---|
| GET | `/config/edit` | Load editable step slice with attribution | `get_editable_config_slice` | `config_editor` | No |
| POST | `/config/update` | Patch field metadata or default in an override file | `update_field_config` | `config_editor` | Yes |
| POST | `/config/reset` | Remove a field override, reverting to base/tool defaults | `reset_field_to_base` | `config_editor` | Yes |
| POST | `/config/presets/add` | Add a preset to a field in an override file | (line 301) | `config_editor` | Yes |
| POST | `/config/presets/remove` | Remove a preset from a field | (line 385) | `config_editor` | Yes |
| GET | `/config/tools` | List available tools | `list_available_tools` | `config_editor` | No |
| GET | `/config/coverage` | Return tool × language coverage matrix | `get_tool_language_coverage` | `config_editor` | No |
| GET | `/config/languages` | List available languages | `list_available_languages` | `config_editor` | No |
| POST | `/config/languages` | Create a new language config file | `create_language` | `config_editor` | Yes |
| GET | `/config/languages/{language_id}/tags` | Return unique preset tags for a language | `get_language_tag_list` | `config_editor` | No |
| GET | `/config/steps` | List visible steps for tool + language | `list_available_steps` | `config_editor` | No |
| GET | `/config/audit` | Paginated audit log | `get_audit_log` | `audit_viewer` | No |
| GET | `/config/history` | List versions for scope + target | `get_config_history` | `audit_viewer` | No |
| GET | `/config/history/diff` | Diff two version numbers | `diff_config_versions` | `audit_viewer` | No |
| GET | `/config/history/{version}` | Return full envelope for a specific version | `get_config_version` | `audit_viewer` | No |

**No restore (rollback) endpoint currently exists.**

```
Status: No restore-to-version endpoint implemented
Migration implication: Restoring a previous version requires a new POST endpoint. The data is available in history files but no write path to apply it is exposed via the API.
```

**Key request/response models:**

- `GET /api/wizard/config/resolved` → `WizardConfig` (Pydantic model, `backend/app/models/wizard.py`)
- `POST /api/generate/preview` → `GenerateRequest` (payload) / `PreviewResponse` (list of `PreviewFile`)
- `POST /api/generate` → `GenerateRequest` (payload) / ZIP `StreamingResponse`
- `POST /config/update` → raw `dict` payload / `EditableStep` (dict)
- `GET /config/edit` → `EditableStep` (dict with `step` + `source_tracking`)

Payload schemas for config editor mutation endpoints (`/config/update`, `/config/reset`, `/config/presets/add`, `/config/presets/remove`) are currently untyped `dict[str, Any]` in the router — they have no Pydantic request model.

```
Migration implication: Adding Pydantic request models to mutation endpoints would be a low-risk improvement that should be included in the first migration ticket.
```

---

### 2. Current Persistence and Database Stack

**Status: No relational database currently exists.**

The entire persistence layer writes to and reads from JSON files on disk under `backend/app/data/wizard_configs/`.

Key findings from `backend/pyproject.toml`:

```
dependencies = [
    "fastapi==0.115.12",
    "uvicorn[standard]==0.34.0",
    "pydantic==2.12.5",
    "python-multipart==0.0.20",
]
```

- **No SQLAlchemy** — not installed, not imported anywhere in the codebase.
- **No Alembic** — no migration framework is configured.
- **No database engine** — no SQLite, PostgreSQL, or any other database connection exists.
- **No database models** — data models are Pydantic only (`backend/app/models/wizard.py`).
- **No session management** — no database session factory, no connection pool.
- **No repository pattern** — service functions read and write files directly.
- **No seed data mechanism** — the `wizard_configs/` directory itself serves as the seed data.
- **No transaction management** — file writes are atomic via `tempfile → os.rename`, but there is no cross-operation transaction boundary.
- **No user table** — no user identity storage exists.

```
Migration implication: The database migration tickets must first introduce DB infrastructure from scratch: engine configuration, Alembic migration setup, session management, local development configuration (likely SQLite locally, PostgreSQL in production), and connection management in FastAPI (dependency injection via `Depends`). This is a prerequisite for all other migration tickets.
```

---

### 3. Existing Test Coverage

**Test infrastructure:** `conftest.py` redirects `DATA_DIR` for all relevant services to a per-session temp copy, preventing tests from mutating production data. History and audit log paths are also patched.

| Test file | Covered behaviour | Missing coverage | Migration implication |
|---|---|---|---|
| `test_config_loader.py` | `get_all_configs`, `get_config`, composition safety (deepcopy), combo override application, combo override priority, missing combo file, language selection | Nested field paths; `get_available_tools`/`get_available_languages`; `extract_presets_from_config`; preset file expansion as a standalone test | Parity tests against DB resolver can be modelled on these patterns |
| `test_config_conformance.py` | Schema validity; every tool/language file; all tool × language combos load without error; file generation produces non-empty output; `validate_override_references` checks for all lang/tool files | No golden-file output comparison; no explicit override resolution order test; no nested field path test | The cross-cutting conformance approach is the right template for DB parity tests |
| `test_config_validator.py` | `validate_wizard_schema`, `validate_tool_override`, `validate_language_override`, `validate_combo_override`, `validate_config_file` | Editability value validation; preset shape validation; `applies_to` validation | Validation tests can be reused post-migration if service-level validation is preserved |
| `test_config_persistence.py` | Atomic write, backup/restore, JSON syntax validation, override schema validation, `save_config`, `ConfigTransaction`, `verify_changes_reloadable` | Race condition / concurrent write; audit append failure isolation; version save failure isolation | DB write tests must cover transaction rollback patterns absent in the current file-based tests |
| `test_version_history.py` | `save_version`, `list_versions`, `get_version`, `get_version_data`, `get_latest_version_number`; integration with `save_config`; audit entry includes version number | No test for concurrent version numbering | Version history DB model tests can follow the same fixture/isolation pattern |
| `test_routes.py` | Health, `GET /api/wizard/configs`, `GET /api/wizard/config/{id}`, `GET /api/wizard/config/resolved`, `GET /api/wizard/config/edit`, `POST /api/generate/preview`, `POST /api/generate` | No tests for config editor mutation endpoints (`POST /config/update`, `POST /config/reset`, `POST /config/presets/add`); no auth integration tests for wizard routes | DB-backed API should pass all existing route tests without modification |
| `test_auth.py` | `AuthUser`, `_extract_user`, `require_config_editor`, `require_audit_viewer`; route integration (403/200 with correct roles) | No test for actor being threaded to audit log on mutation | Migration can preserve auth behaviour; DB migration does not require changing auth |
| `test_file_generator.py` | Markdown rendering, verbatim rendering, frontmatter rendering, text rendering, locked value, multi-step same file, repeatable groups, agent_list | No test for path traversal in output filenames; no test comparing generated output to fixed expected strings | No golden-file tests exist; these should be added before DB cutover |
| `test_config_diff.py`, `test_config_editor.py`, `test_config_patcher.py` | Config diff, editor slice extraction, patch operations | — | Patcher tests confirm the mutation path; they use file fixtures that will need DB equivalents |
| `test_enums.py` | Enum values | — | Low risk |

**No snapshot or golden-file tests exist.** Generated file content is tested only for non-emptiness, not for exact content.

**Minimum parity tests required before DB cutover:**

1. JSON resolver output vs DB resolver output for every supported tool/language combination (`claude+python`, `claude+java`, `copilot+typescript`, `copilot+react-typescript`, `cursor+java`, `cursor+react-typescript`).
2. Generated file output comparison for the same selected answers before and after migration.
3. Override source attribution comparison — `override_source` values must match between JSON and DB resolvers.
4. Preset expansion comparison — resolved `presets` arrays must be identical before and after migration.
5. Hidden step and hidden field comparison — the set of visible steps returned by `strip_hidden_steps` must match.
6. Nested field override comparison — a `metadata_override` targeting a nested path (e.g. `rule_files.rules.rule_file_name`) must resolve identically.
7. Combo override priority test — combo overrides must take precedence over tool and language layers in the DB resolver.

---

### 4. Generated File Behaviour

**Generator entry point:** `generate_files(config: WizardConfig, answers: Answers) -> dict[str, str]`
**Source file:** `backend/app/services/file_generator.py`

The function returns a `dict[str, str]` mapping output file paths to generated content. It does **not** write files to disk. The caller (`generate.py` router) passes this dict to `zip_service.py` to package it as a ZIP, or returns it directly as JSON in the preview response.

**Output formats supported in code:**

| Format | Renderer | Notes |
|---|---|---|
| `markdown` | `_render_markdown` | `# heading` + `## label` sections per field |
| `markdown_frontmatter` | `_render_markdown_frontmatter` | YAML front matter block for fields with `frontmatter=True`, then markdown body |
| `verbatim` | `_render_verbatim` | Returns the `content` field value as-is |
| `text` | `_render_text` | `key: value` pairs |

There is no `json` renderer in code despite `json` appearing as an `OutputFormat` enum value. Steps with `output_format: json` would fall through to the `text` renderer.

**Multi-file generation:**

- `agent_list` fields generate **one file per agent** in `field.agent_config.output_dir`. The filename is `{agent_name}{file_suffix}`.
- `repeatable_group` fields generate **one file per entry** for steps with a directory `output_file` (ending in `/`). The filename is resolved from `rule_file_name`, `file_name`, or similar candidate keys in the entry dict.
- Multiple steps with the **same `output_file`** path are rendered independently and joined with `\n\n` in the final dict.

**Directory output resolution:** `_resolve_directory_output` and `_resolve_directory_output_for_entry` handle steps where `output_file` ends in `/`. They check candidate keys in step answers for a filename, falling back to a default derived from the step ID.

**Path traversal:** No path traversal prevention exists. A `rule_file_name` value of `../../etc/passwd` would produce the path `.cursor/rules/../../etc/passwd` in the output dict without sanitisation. The ZIP endpoint packages these paths as-is. This is a **security concern** for the migration.

```
Migration implication: Output path sanitisation must be added before or during the database migration. Generated file paths should be validated to prevent path traversal in the ZIP output.
```

**Determinism:** For the same `WizardConfig` and `answers`, `generate_files` always produces the same output. No timestamps, random IDs, or side effects are introduced during generation.

**Output format validation:** The `output_format` field is validated by Pydantic via the `OutputFormat` enum. Invalid values are rejected at config load time.

---

### 5. Config Editor Permission Model

**Source file:** `backend/app/services/auth.py`

The current auth model is a lightweight **header-based role system** controlled by an `AUTH_ENABLED` environment variable.

Key findings from `test_auth.py` (the source file is excluded from Copilot access):

- **`AuthUser`** is a frozen dataclass with `username: str` and `roles: frozenset[str]`.
- When `AUTH_ENABLED=false` (the default), every request is treated as the anonymous user with no roles. All `require_config_editor` and `require_audit_viewer` checks pass unconditionally.
- When `AUTH_ENABLED=true`, identity is extracted from two request headers:
  - `x-auth-user`: username string (required; 401 if missing or blank)
  - `x-auth-roles`: comma-separated role list (optional; defaults to empty roles)
- **Two roles exist:**
  - `ROLE_CONFIG_EDITOR = "config_editor"` — required for all mutation endpoints and read endpoints in `/config/`
  - `ROLE_AUDIT_VIEWER = "audit_viewer"` — required for `/config/audit` and `/config/history*`
- No admin role, group claim, allow-list, or permission table exists.
- No approval workflow exists.
- **The authenticated user (`actor`) is not threaded to the persistence layer.** All calls to `config_patcher.py → _write_json_file` pass `context={"scope": ..., "target": ...}` without an `actor`. The audit log records `actor="system"` for all saves.
- There is no way to distinguish who edited a draft vs who approved it.

```
Status: No config-editor-specific permission model beyond basic role gating found.
Migration implication: The database migration can preserve current behaviour initially (AUTH_ENABLED flag + header roles). However:
1. The actor should be threaded from the authenticated user through to save_config and the audit log before or during migration.
2. Editor write APIs should not be expanded (e.g. bulk edits, approval workflows) until role/approval semantics are defined.
3. A user table will be required for user-owned revisions and template promotion workflows described in the User Revisions vs Shared Templates section.
```

---

### 6. Current Config Save and Versioning Semantics

**Source files:** `backend/app/services/config_persistence.py`, `backend/app/services/version_history.py`

**What happens when `save_config` is called (`config_patcher._write_json_file` always routes through it):**

1. `_validate_json_syntax(data)` — confirms data is JSON-serialisable. Always runs.
2. `validate_config_file(file_path, data)` — validates against Python schema validators (`config_validator.py`). Runs when `validate=True` (the patcher calls with `validate=False` because override files are partial by design).
3. Read existing file content for audit diff (non-fatal, best-effort).
4. Create `.backup` file alongside original (`create_backup=True` by default). Overwrites any existing `.backup`.
5. Write to `tempfile.mkstemp` in the same directory.
6. Verify temp file is valid JSON.
7. `temp_path.replace(file_path)` — atomic POSIX rename.
8. Verify written file is readable.
9. Optionally call `_verify_config_reloadable` (not called by the patcher).
10. Build and emit audit log entry (`audit_log.append_audit_entry`) — **non-fatal**: wrapped in `try/except`, failure only prints to stderr.
11. Inside the audit block, call `version_history.save_version` — **non-fatal**: also wrapped in `try/except`, failure only prints to stderr.

**Atomicity and failure modes:**

| Scenario | Outcome |
|---|---|
| Audit append fails after file write | File is already written. Audit entry is lost. No rollback. |
| Version save fails after file write | File is already written. Version is not recorded. No rollback. |
| Version save and audit both fail | File is written but neither audit nor history records the change. |
| Two concurrent saves to the same file | Both use `tempfile → rename`. The last rename wins silently. Both may compute the same next version number and write the same `v{NNN}.json` path, causing one version to be overwritten. No file lock is used. |

**Actor determination:** The `actor` is derived from `context.get("actor", "system")`. The patcher passes `context={"scope": ..., "target": ...}` without an `actor` key, so all saves are recorded with `actor="system"`.

**Summary generation:** `build_audit_entry` in `audit_log.py` generates the summary string describing what changed. The `save_version` call uses this summary.

**Restore:** No restore endpoint exists. The version data is accessible via `GET /config/history/{version}` but there is no write path to apply a previous version to the current override file.

```
Migration implication:
- The non-fatal audit and version save must become part of a database transaction so that file write, audit entry, and version record are atomic.
- The race condition in version numbering must be resolved via a database sequence or `SELECT ... FOR UPDATE`.
- A restore endpoint must be added: POST /config/history/restore or similar.
- The actor must be threaded from the authenticated user to the persistence context.
```

---

### 7. Current Data Validation Rules

**Source files:** `backend/app/services/config_validator.py`, `backend/app/data/wizard_configs/override.schema.json`, `backend/app/models/wizard.py`

The backend uses a **custom Python validator** (`config_validator.py`). The `jsonschema` library is not installed; validation is hand-written.

| Validation check | When it runs | Source |
|---|---|---|
| `schema_version` + `steps` array present in `schema.json` | Load time | `validate_wizard_schema` |
| Each step has `id`, `title`, `fields` | Load time | `validate_wizard_schema` |
| Each field has `id`, `type`, `label` | Load time | `validate_wizard_schema` |
| `tool_id` present in tool override | Load time + save time | `validate_tool_override` |
| `language_id` present in language override | Load time + save time | `validate_language_override` |
| `metadata_overrides`, `field_overrides`, `step_overrides` are arrays if present | Load time + save time | all override validators |
| Each `metadata_override` has `field_id` | Load time + save time | all override validators |
| Each `field_override` has `field_id` | Load time + save time | all override validators |
| Each `step_override` has `step_id` | Load time + save time | all override validators |
| `field_id` paths reference real fields in `schema.json` (semantic) | Load time only | `validate_override_references` (in loader, conformance tests) |
| Preset `label` and `value` present | Conformance tests only | `test_config_conformance.py` |
| Editability values are `free/locked/suggested/defaulted` | Conformance tests only | `test_config_conformance.py` |
| Field types are a known enum | Pydantic model load | `WizardField.type` via `FieldType` enum |
| Output formats are a known enum | Pydantic model load | `WizardStep.output_format` via `OutputFormat` enum |
| `applies_to` filter (tool/language match) | Load time (silently skipped) | `_apply_overrides` |

**Validation gaps:**

- `field_id` path validity is **not validated at save time**. A save via `/config/update` with an invalid `field_id` path (e.g. `nonexistent_step.nonexistent_field`) will write to disk without error. The override will be silently ignored at load time.
- Nested field paths (e.g. `rule_files.rules.rule_file_name`) are resolved at load time by `_find_nested_field` but are not validated at save time.
- `editability` values are validated in conformance tests but not in the runtime save path.
- Preset object shape (`label`, `value`) is validated in conformance tests only.
- The `applies_to` object is not validated for correct structure.
- No frontend-only validation has been identified in the reviewed code. The frontend relies on backend validation.

```
Migration implication: The database migration should introduce database-level constraints (foreign keys, enum columns) and service-level validation for field_id path resolution at save time. This will close the current gap where invalid overrides are accepted but silently ignored.
```

---

### 8. Current Frontend Assumptions

**Key frontend files:** `frontend/src/api/wizardApi.ts`, `frontend/src/types/wizard.ts`, `frontend/src/hooks/useWizard.ts`, `frontend/src/components/Wizard.tsx`

**Hidden step filtering:** The frontend filters hidden steps itself. In `useWizard.ts` line 14: `if (step.hidden) continue`. The backend's `strip_hidden_steps` also removes hidden steps from `GET /api/wizard/config/resolved`. Hidden steps are therefore filtered at both layers for the wizard flow.

**Hidden field filtering:** The frontend receives fields as returned by the backend. Fields with `hidden: true` are not explicitly filtered by the frontend in the reviewed code — the backend wizard endpoint returns them as part of the step and the frontend renders them unless they handle `hidden` at component level.

**`override_source` dependency:** The `EditableField` TypeScript type includes `override_source?: string` and `source_file?: string`. The `ConfigEditor` and `StepFieldEditor` components use the config editor API which returns these fields. The frontend depends on this shape.

**Editability dependency:** The `EditableField` type includes `editability: Editability` (`free | locked | suggested | defaulted`), `is_locked: boolean`, `is_default: boolean`. The `FieldGroup` component tests (`FieldGroup.test.tsx`) explicitly test grouping of fields by `is_locked`, `is_default`, and `editability`. **The frontend depends on these fields being present in the response.**

**Field order:** The frontend renders fields in the order returned from the backend. Step and field order from the JSON is preserved through the resolver and Pydantic model. The frontend does not sort or reorder.

**Nested fields:** The `WizardField` TypeScript type has `fields?: WizardField[]`, confirming nested field support. `useWizard.ts` validates nested fields inside `repeatable_group` entries.

**Repeatable groups and agent_list:** Both are supported in the frontend. `WizardCopilotRepeatable.test.tsx` tests repeatable group behaviour. `AgentFieldConfig` and `AgentEntry` types exist in `types/wizard.ts`.

**Preset tags:** The `Preset` type includes `tags?: string[]`. The `tag_source` mechanism allows the active language selection to filter visible presets.

**API shape dependency:** `fetchConfigs`, `fetchWizardConfig`, `fetchEditableConfig` are typed and rely on the exact backend JSON response shape. Any change to field names or nested structure in the response would require a corresponding frontend change.

**Frontend tests:** `FieldGroup.test.tsx`, `WizardCopilotRepeatable.test.tsx`, `GeneratePreview.test.tsx`, `AuditDiffPanels.test.tsx`, `ErrorBoundary.test.tsx`, `wizardApi.test.ts`, `App.test.tsx` exist. Tests cover component rendering and grouping logic but not end-to-end integration against a real API.

```
Migration implication:
- The backend database resolver must return the exact same JSON shape as the current JSON resolver.
- The override_source, is_locked, is_default, and editability fields must be present in the EditableStep response.
- Hidden step filtering is redundant (both layers filter) but both must continue to work correctly.
- No frontend changes are required during the first migration phase if the API response shape is preserved.
```

---

### 9. Supported Tool/Language Matrix

**Current tool IDs:** `claude`, `copilot`, `cursor` (discovered from `backend/app/data/wizard_configs/tools/*.json`)

**Current language IDs:** `angular`, `dotnet`, `java`, `python`, `react-typescript`, `typescript` (discovered from `backend/app/data/wizard_configs/languages/*.json`)

All tools are valid with all languages. No combinations are intentionally unsupported. The language override is optional — a missing language file is silently skipped and the tool config loads without language-specific overrides.

**Combo overrides:** The `overrides/` directory is currently empty. Combo override support exists in code (`load_composable_config` checks for `overrides/{tool_id}+{language_id}.json`) and is tested in `test_config_loader.py`, but no production combo files exist yet.

| Tool | Language | Supported? | Tool file | Language file | Combo override |
|---|---|---|---|---|---|
| claude | angular | Yes | `tools/claude.json` | `languages/angular.json` | None |
| claude | dotnet | Yes | `tools/claude.json` | `languages/dotnet.json` | None |
| claude | java | Yes | `tools/claude.json` | `languages/java.json` | None |
| claude | python | Yes | `tools/claude.json` | `languages/python.json` | None |
| claude | react-typescript | Yes | `tools/claude.json` | `languages/react-typescript.json` | None |
| claude | typescript | Yes | `tools/claude.json` | `languages/typescript.json` | None |
| copilot | angular | Yes | `tools/copilot.json` | `languages/angular.json` | None |
| copilot | dotnet | Yes | `tools/copilot.json` | `languages/dotnet.json` | None |
| copilot | java | Yes | `tools/copilot.json` | `languages/java.json` | None |
| copilot | python | Yes | `tools/copilot.json` | `languages/python.json` | None |
| copilot | react-typescript | Yes | `tools/copilot.json` | `languages/react-typescript.json` | None |
| copilot | typescript | Yes | `tools/copilot.json` | `languages/typescript.json` | None |
| cursor | angular | Yes | `tools/cursor.json` | `languages/angular.json` | None |
| cursor | dotnet | Yes | `tools/cursor.json` | `languages/dotnet.json` | None |
| cursor | java | Yes | `tools/cursor.json` | `languages/java.json` | None |
| cursor | python | Yes | `tools/cursor.json` | `languages/python.json` | None |
| cursor | react-typescript | Yes | `tools/cursor.json` | `languages/react-typescript.json` | None |
| cursor | typescript | Yes | `tools/cursor.json` | `languages/typescript.json` | None |

Any `language` string not matching a known file is silently accepted — the loader skips the language override and returns the tool config only. There is no explicit validation that the requested `language` is in the known set (confirmed in wizard router: `"Language validation is not strict — any language string is accepted"`).

```
Migration implication: The database should enforce referential integrity between tool_id and language_id. Unknown language IDs should return a 400 rather than silently succeeding.
```

---

### 10. Jira Planning Implications

Based on the findings above:

**DB infrastructure must come first.** No database stack exists. The first ticket must introduce SQLAlchemy, Alembic, session management via FastAPI `Depends`, and local/deployed engine configuration. Nothing else in the migration can proceed until this is in place.

**Add API compatibility tests before schema work.** The wizard route tests in `test_routes.py` cover the read-only wizard API but not the mutation endpoints. Before migrating the persistence layer, add integration tests that assert the exact request/response shape for `/config/update`, `/config/reset`, `/config/presets/add`, and `/config/presets/remove`. These will serve as regression guards during migration.

**Add file generation parity tests before DB cutover.** No golden-file tests currently exist. Before switching the resolver to database-backed, create snapshot tests that record the exact generated file output for each supported tool/language combination. These are the primary correctness signal for cutover.

**Thread the actor before expanding editor write APIs.** The authenticated user is never propagated to the audit log. This should be fixed as part of the first migration ticket that touches `config_patcher.py`, before any new write endpoints are added.

**Defer permission and approval work.** The current role model (`config_editor`, `audit_viewer`) is sufficient to gate the first migration. User-owned revisions, template promotion, and approval workflows require a user table and are out of scope for the first migration epic.

**Keep legacy JSON history read-only.** Do not attempt to import historical `v{NNN}.json` snapshot files into the database during the first migration. Start database-backed versioning from the cutover date.

**Defer preset database migration.** Preset content in language/tool files is large and complex. Preset expansion behaviour must remain file-based until the core schema, override, and resolver migration is proven. A dedicated preset migration ticket should follow.

**No frontend changes required immediately.** The backend must preserve the existing API response shape. If the DB-backed resolver returns the same JSON for the same inputs, no frontend changes are needed for the first migration phase.

**Add path traversal validation before or during migration.** The current file generator does not sanitise `output_file` paths derived from user input. This should be addressed as a security fix in a separate ticket, not deferred past the migration.

---

## Recommended Database Migration Strategy

The database migration should preserve the existing layered composition model rather than flattening everything into final resolved templates.

Recommended conceptual model:

```
Base schema
+ ordered override layers
+ deterministic resolver
= resolved wizard config
```

The database should make this model easier to govern, audit, query, and edit.

Recommended first milestone: The database-backed resolver produces the same normalised resolved config as the JSON-backed resolver for every supported tool/language combination.

Recommended comparison test combinations:

```
claude + python
claude + java
copilot + typescript
copilot + react-typescript
cursor + java
cursor + react-typescript
```

Do not switch the runtime default from JSON to database until these parity tests pass.

Recommended long-term architecture:

```
Database            = canonical configuration model
JSON                = import/export/review format
Generated files     = output artifacts
Legacy JSON history = read-only archive unless explicitly migrated
```
