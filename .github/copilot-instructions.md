# AI Accelerator — Copilot Instructions

## Purpose
AI Accelerator is a configuration-driven system for generating AI tool setups (Claude, GitHub Copilot, Cursor) using composable JSON configurations.

The backend provides:
- Config composition (base + overrides)
- Schema validation
- Patch application
- Config diffing
- File generation

The system must remain deterministic, testable, and extensible.

---

## Non-Negotiable Rules

- Follow existing architecture and patterns strictly
- Prefer minimal, targeted changes over large rewrites
- Do not introduce breaking changes unless explicitly required
- Do not duplicate logic that already exists
- Always keep business logic in the service layer
- Remove redundant code and configurations when possible


---

## File Creation Guardrails

- Never create new Markdown files that summarize work performed
- Do not create files such as:
  - `SUMMARY.md`
  - `CHANGES.md`
  - `TASK_NOTES.md`
  - `IMPLEMENTATION_SUMMARY.md`
  - `MIGRATION_NOTES.md`
- Summaries must be returned in chat, not written to the repository
- Only create or modify `.md` files if explicitly requested
- Prefer updating existing documentation rather than creating new files

---

## Architecture Overview

### Backend (FastAPI)
- `app/main.py` → API entry point
- `app/routers/` → HTTP layer (must remain thin)
- `app/services/` → ALL business logic
- `app/models/` → Pydantic models
- `app/data/wizard_configs/` → JSON configuration files
- `app/schemas/` → JSON schema definitions

### Frontend (React + TypeScript)
- UI for interacting with configuration system
- Consumes backend API

---

## Core Services (Source of Truth)

- `config_loader.py` → Load and merge configs
- `config_validator.py` → Validate against schemas
- `config_patcher.py` → Apply structured patches
- `config_diff.py` → Compare configurations
- `file_generator.py` → Generate output files

Always use these services. Do not reimplement their logic elsewhere.

---

## Code Modification Rules

- Keep routers thin (no business logic)
- All logic must live in `app/services/`
- Do not change function signatures unless necessary
- Do not remove or weaken validation
- Do not hardcode values that belong in configuration
- Reuse existing utilities before adding new ones
- Keep changes small and focused
- Backwards compatibility is a NOT required and clean up is encouraged

---

## Configuration Rules

- JSON configuration is the source of truth
- Use composable structure: base + tool + language + overrides
- All configs must remain schema-valid

### If modifying configuration structure:
- Update JSON schema
- Update validator logic
- Update tests

---

## Common Change Patterns

### Add a New Config Field
1. Update JSON schema
2. Update validator
3. Update loader if required
4. Add tests

---

### Modify Existing Behaviour
1. Locate the responsible service
2. Make minimal change
3. Preserve backwards compatibility
4. Update tests

---

### Add a New Service
1. Create in `app/services/`
2. Keep logic reusable and isolated
3. Add unit tests
4. Integrate via router if needed

---

### Add API Endpoint
1. Implement logic in service layer
2. Expose via router
3. Keep router thin
4. Add tests

---

## Testing Expectations

- All changes must pass existing tests
- New functionality must include tests
- Prefer unit tests for service logic
- Avoid fragile or tightly coupled tests

---

## Anti-Patterns (Avoid)

- Adding business logic in routers
- Duplicating logic across services
- Bypassing validation layers
- Hardcoding configuration values
- Large, unscoped refactors
- Creating unnecessary documentation files

---

## Key Entry Points

- API entry: `app/main.py`
- Config loading: `config_loader.py`
- Validation: `config_validator.py`
- Patching: `config_patcher.py`
- Diffing: `config_diff.py`
- File generation: `file_generator.py`

---

## Output Expectations

- Outputs must be deterministic
- Generated files must reflect configuration exactly
- Do not manually modify generated files
- Prefer structured outputs over free-form text

---

## Operating Mode

- Default to safe and conservative changes
- Optimise for correctness over speed
- Prefer explicit logic over implicit behaviour
- When uncertain, follow existing patterns in the codebase