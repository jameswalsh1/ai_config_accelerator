# Composable Configuration System - Practical Examples

## Example 1: Create a New Language Override

Scenario: You want to add Rust support to all tools.

### Step 1: Create `languages/rust.json`

```json
{
  "language_id": "rust",
  "version": "1.0",
  "applies_to": {
    "languages": ["rust"]
  },
  "metadata_overrides": [
    {
      "field_id": "language_selection.language",
      "editability": "suggested"
    }
  ],
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "merge_presets": [
        {
          "label": "Actix-web + tokio",
          "description": "High-performance async web framework",
          "value": "- Runtime: Tokio async executor\n- Framework: Actix-web 4.x\n- ORM: Diesel or sqlx\n- Serialization: Serde\n- Testing: built-in test framework",
          "tags": ["rust"],
          "mode": "append"
        },
        {
          "label": "Axum + sqlx",
          "description": "Modern modular web framework from Tokio team",
          "value": "- Runtime: Tokio\n- Framework: Axum\n- Database: sqlx with compile-time verification\n- Serialization: Serde\n- Error handling: anyhow, thiserror",
          "tags": ["rust"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    },
    {
      "field_id": "claude_md.coding_conventions",
      "merge_presets": [
        {
          "label": "Rust conventions",
          "description": "Idiomatic Rust practices",
          "value": "## Naming & Style\n- Variables/functions: snake_case\n- Types/traits: PascalCase\n- Constants: UPPER_SNAKE_CASE\n- Follow clippy recommendations: `cargo clippy`\n\n## Error Handling\n- Use Result<T, E> for recoverable errors\n- Implement Error trait for custom errors\n- Use ? operator for error propagation\n- Avoid panic! except in tests or fatal scenarios",
          "tags": ["rust"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    }
  ],
  "step_overrides": []
}
```

### Step 2: It works!

When you load any tool with Rust:
```python
config = load_composable_config("claude", "rust")
config = load_composable_config("copilot", "rust")
config = load_composable_config("cursor", "rust")
# All get Rust presets automatically
```

---

## Example 2: Create a Tool-Specific Override

Scenario: GitHub Copilot needs to customize how presets are rendered.

### Modify `tools/copilot.json`

```json
{
  "tool_id": "copilot",
  "tool_metadata": {
    "title": "GitHub Copilot Configuration",
    "description": "Generate repository-wide custom instructions...",
    "target": "copilot",
    "output_preview_targets": [ /* ... */ ]
  },
  "version": "1.0",
  "applies_to": {
    "tools": ["copilot"]
  },
  "metadata_overrides": [
    {
      "field_id": "language_selection.language",
      "editability": "free"
    }
  ],
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "merge_presets": [
        {
          "label": "Copilot Enterprise features",
          "description": "Use Copilot Enterprise capabilities",
          "value": "Consider using Copilot Enterprise features:\n- Code reviews with Copilot\n- Policy enforcement\n- Custom models training",
          "tags": ["copilot-enterprise"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    }
  ],
  "step_overrides": []
}
```

---

## Example 3: Create a Tool + Language Special Case

Scenario: Python + JetBrains needs specific IDE configuration.

### Create `overrides/jetbrains+python.json`

```json
{
  "tool_id": "jetbrains",
  "language_id": "python",
  "version": "1.0",
  "applies_to": {
    "tools": ["jetbrains"],
    "languages": ["python"]
  },
  "metadata_overrides": [],
  "field_overrides": [
    {
      "field_id": "claude_md.coding_conventions",
      "merge_presets": [
        {
          "label": "PyCharm/IDEA Python setup",
          "description": "JetBrains IDE specific Python configuration",
          "value": "## IDE Configuration\n- Run Inspections: Preferences → Editor → Inspections\n- Code Style: Enforce PEP 8 via Inspections\n- Type hints: Enable type checker in Editor → Python Integrated Tools\n- Testing: Configure pytest in Run → Edit Configurations",
          "tags": ["jetbrains", "python"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    }
  ],
  "step_overrides": []
}
```

**Result**: This override only applies when loading `jetbrains + python`. Other combinations use generalized overrides.

---

## Example 4: Lock a Field for a Tool

Scenario: For your internal tool, you want to lock the language selection.

### Create `tools/internal-tool.json`

```json
{
  "tool_id": "internal-tool",
  "tool_metadata": {
    "title": "Internal Project Configuration",
    "description": "Configuration for internal projects",
    "target": "internal"
  },
  "version": "1.0",
  "applies_to": {
    "tools": ["internal-tool"]
  },
  "metadata_overrides": [
    {
      "field_id": "language_selection.language",
      "editability": "locked",
      "default": "typescript"
    }
  ],
  "field_overrides": [],
  "step_overrides": []
}
```

**Result**: When users load this tool, the language is locked to TypeScript.

---

## Example 5: Replace All Presets for a Field

Scenario: Simplify the tech stack options for beginners.

### Create `languages/beginner.json`

```json
{
  "language_id": "beginner",
  "version": "1.0",
  "applies_to": {
    "languages": ["beginner"]
  },
  "metadata_overrides": [],
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "replace_presets_with": [
        {
          "label": "Python + FastAPI",
          "description": "Simple, modern Python backend",
          "value": "- Backend: Python 3.11+ with FastAPI\n- Database: SQLite for simplicity\n- Testing: pytest\n- Deployment: Render or Railway",
          "tags": ["beginner", "python"],
          "mode": "replace"
        },
        {
          "label": "TypeScript + Express",
          "description": "Familiar Node.js backend",
          "value": "- Backend: Node.js with Express\n- Database: SQLite for simplicity\n- Testing: Jest\n- Deployment: Vercel or Railway",
          "tags": ["beginner", "typescript"],
          "mode": "replace"
        }
      ],
      "merge_mode": "replace"
    }
  ],
  "step_overrides": []
}
```

**Note**: Use `merge_mode: "replace"` when `replace_presets_with` is used.

---

## Example 6: Hide a Step for Specific Users

Scenario: For a fully managed service, hide the verification policy step.

### Create `overrides/managed-service+all-languages.json`

```json
{
  "tool_id": "managed-service",
  "version": "1.0",
  "applies_to": {
    "tools": ["managed-service"]
  },
  "metadata_overrides": [],
  "field_overrides": [],
  "step_overrides": [
    {
      "step_id": "verification_policy",
      "hidden": true
    }
  ]
}
```

**Result**: The verification policy step is hidden from the UI.

---

## Practical Workflow: Adding Support for a Framework

Scenario: Add support for Next.js+App Router across all tools and languages.

### 1. Check if you need a language override

Next.js is a framework, not a language. It's TypeScript-specific, so it goes in `languages/next-app-router.json`:

```json
{
  "language_id": "next-app-router",
  "version": "1.0",
  "applies_to": {
    "languages": ["next-app-router"]
  },
  "field_overrides": [
    {
      "field_id": "claude_md.tech_stack",
      "merge_presets": [
        {
          "label": "Next.js + App Router",
          "description": "Modern React with Next.js 14+ App Router",
          "value": "- Frontend: React 19 + Next.js 14+ (App Router)\n- Styling: Tailwind CSS\n- API: Route handlers in app/api/\n- Database: Prisma + PostgreSQL\n- Deployment: Vercel\n- Testing: Vitest + React Testing Library",
          "tags": ["next-app-router", "typescript", "react"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    },
    {
      "field_id": "claude_md.coding_conventions",
      "merge_presets": [
        {
          "label": "Next.js App Router best practices",
          "value": "## File Structure\napp/\n  api/              # Route handlers\n  (auth)/           # Route groups\n  layout.tsx        # Root layout\n  page.tsx          # Root page\n\n## Key Practices\n- Use Server Components by default\n- Use 'use client' only when needed (events, hooks)\n- Co-locate data fetching with components\n- Use Parallel Routes for complex UIs\n- App Router metadata (not Next.js Head)",
          "tags": ["next-app-router"],
          "mode": "append"
        }
      ],
      "merge_mode": "append"
    }
  ]
}
```

### 2. It works for all tools!

```python
# All of these automatically get Next.js support
config = load_composable_config("claude", "next-app-router")
config = load_composable_config("copilot", "next-app-router")
config = load_composable_config("cursor", "next-app-router")
```

### 3. If you need tool-specific tweaks, create an override

E.g., if Claude needs additional MCP server recommendations for Next.js:

Create `overrides/claude+next-app-router.json`:
```json
{
  "tool_id": "claude",
  "language_id": "next-app-router",
  "field_overrides": [
    {
      "field_id": "mcp_config.content",
      "merge_presets": [
        {
          "label": "Next.js MCP Server",
          "value": "{\"mcpServers\": {\"next-inspector\": {...}}}",
          "mode": "append"
        }
      ]
    }
  ]
}
```

---

## Testing Your Overrides

```python
from app.services.config_loader_composable import load_composable_config

# Test your new override
try:
    config = load_composable_config("claude", "rust")
    print("✓ Config loaded successfully")
    
    # Verify presets were merged
    for step in config['steps']:
        if step['id'] == 'claude_md':
            for field in step['fields']:
                if field['id'] == 'tech_stack':
                    presets = field.get('presets', [])
                    rust_presets = [p for p in presets if 'rust' in p.get('tags', [])]
                    print(f"✓ Found {len(rust_presets)} Rust presets")
except Exception as e:
    print(f"✗ Error: {e}")
```

---

## Key Takeaways

1. **Language overrides** apply to all tools (use when framework/language-specific)
2. **Tool overrides** apply to all languages (use when tool-specific)
3. **Tool+Language overrides** only when both matter (use sparingly)
4. **Override files are tiny** — only specify what differs
5. **Presets are tagged** — use tags to identify which language/tool they belong to
6. **Merge modes matter** — append, merge_by_label, or replace
7. **Editability metadata** — lock, suggest, default, or free edit

---

## Common Patterns

### Pattern 1: "Add X preset for this language/tool"
→ Use `merge_presets` with `merge_mode: "append"`

### Pattern 2: "Replace all presets with a simplified set"
→ Use `replace_presets_with` with `merge_mode: "replace"`

### Pattern 3: "Update a preset that already exists"
→ Use `merge_presets` with `merge_mode: "merge_by_label"` (if label exists, it's replaced)

### Pattern 4: "Make this field read-only"
→ Add to `metadata_overrides` with `editability: "locked"`

### Pattern 5: "Pre-fill this field but let users change it"
→ Add to `metadata_overrides` with `editability: "defaulted"` and set `default`

---

For more details, see:
- `ARCHITECTURE.md` — Design principles
- `override.schema.json` — Valid override format
- `config_loader_composable.py` — Implementation
