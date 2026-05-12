# Phase 2 — JSON-to-Database Import Workflow

## Overview

Phase 2 introduces a relational database backend for the AI Accelerator configuration system. The database is an **optional, parallel** data source. JSON files remain the runtime default.

---

## Architecture

```
JSON files (source of truth)
    ↓
Import services (app/services/import_/)
    ↓
MySQL / SQLite DB (ORM models via SQLAlchemy)
    ↓
DatabaseConfigReadRepository
    ↓
Feature flag: CONFIG_SOURCE=database
```

---

## Import Process

The import is **idempotent** — it can be run multiple times safely. On re-runs:
- Unchanged records → `unchanged`
- Updated records → `updated`
- New records → `created`

### Import Order (required)

1. **Tools and languages** — creates `ai_tool` and `language` rows
2. **Schema** — creates `config_schema`, `config_step`, `config_field` rows
3. **Layers** — creates `config_layer`, override rows (resolves references to schema rows)

---

## Running the Import

### Dry Run (no DB writes)

```bash
cd backend
uv run python -m app.commands.import_json_to_db --dry-run
```

### Full Import

```bash
cd backend
uv run python -m app.commands.import_json_to_db
```

### Custom Data Directory

```bash
uv run python -m app.commands.import_json_to_db --data-dir /path/to/wizard_configs
```

### Custom DB URL

```bash
uv run python -m app.commands.import_json_to_db --db-url sqlite+aiosqlite:///local.db
```

---

## Makefile Targets

```bash
make db-import          # Run full import
make db-import-dry-run  # Dry run (no writes)
make db-readiness       # Check import status via API
```

---

## Switching to Database Source

Set the environment variable before starting the application:

```bash
CONFIG_SOURCE=database uvicorn app.main:app
```

Or add to `.env`:

```dotenv
CONFIG_SOURCE=database
```

> **Note**: The JSON files are **not removed** when using `CONFIG_SOURCE=database`. The database resolver is a parallel implementation.

---

## Checking Import Status

```bash
curl http://localhost:8000/health/config-db
```

Response when ready:

```json
{
  "database_config_ready": true,
  "active_schema": "2.0",
  "tools": 3,
  "languages": 6,
  "layers": {
    "tool": 3,
    "language": 6,
    "combo": 0
  }
}
```

Response when not ready:

```json
{
  "database_config_ready": false,
  "reason": "no active schema"
}
```

---

## Database Models

| Table | Purpose |
|---|---|
| `ai_tool` | Available AI tools (claude, copilot, cursor) |
| `language` | Available languages (python, typescript, …) |
| `config_schema` | Schema version metadata |
| `config_step` | Wizard steps |
| `config_field` | Wizard fields (supports nesting via self-FK) |
| `config_layer` | Tool/language/combo override layers |
| `config_step_override` | Per-step overrides per layer |
| `config_field_metadata_override` | Field default/editability/required/hidden overrides |
| `config_field_content_override` | Field options/presets/preset_files overrides |
| `config_audit_event` | Immutable audit log |
| `config_version` | Versioned config snapshots |

---

## Running Alembic Migrations

```bash
cd backend
uv run alembic upgrade head
```

---

## Running Parity Tests

Parity tests compare JSON and DB resolvers for the same tool+language combos:

```bash
cd backend
uv run pytest tests/test_db_parity.py -v
```

These tests use in-memory SQLite (aiosqlite) and do not require a live MySQL instance.
