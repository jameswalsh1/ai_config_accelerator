# Database Conventions

> Internal reference for the AI Accelerator backend.
> Scope: Phase 1 — infrastructure baseline (no application tables yet).

---

## Table Naming

- Use **snake_case** plural nouns: `config_templates`, `override_layers`, `version_entries`.
- Prefix related tables with a shared domain name: `config_template`, `config_override`, `config_version`.
- Join/association tables use both entity names joined by `_`: `template_language`.
- Avoid reserved SQL keywords as table names.

## Primary Keys

- Every table uses a surrogate integer primary key named `id`.
- `id` is defined as `Mapped[int] = mapped_column(primary_key=True)`.
- Natural keys (e.g. `tool_id`, `language_id`) are modelled as unique columns, not as primary keys.

## Timestamp Columns

- Every table that needs change tracking inherits `AuditMixin` from `app.db.mixins`.
- `created_at` — UTC timestamp set on insert, never updated.
- `updated_at` — UTC timestamp set on insert and updated on every write.
- All timestamps are stored in UTC using `DateTime(timezone=True)`.
- Use `datetime.now(timezone.utc)` — never `datetime.utcnow()` (deprecated).

## Enum Storage

- Prefer `String` columns with application-level validation over database `ENUM` types.
- MySQL `ENUM` columns make schema migrations difficult; string columns can be altered safely.
- The allowed values are enforced by Pydantic at the API boundary and by Python validators in service code.
- Example: editability is stored as `VARCHAR(32)` with allowed values `free`, `locked`, `suggested`, `defaulted`.

## JSON Column Usage

- Use `JSON` columns only for genuinely schemaless or frequently-changing structures (e.g. preset values, validation rules, agent config blobs).
- Do not use JSON columns as a workaround for missing normalisation.
- Every JSON column must have a Python type annotation in the ORM model.
- Avoid querying inside JSON columns in MySQL — prefer extracting structured values into their own columns.

## Audit Columns

All write-capable tables inherit from `AuditMixin` (see `app/db/mixins.py`):

| Column | Type | Description |
|---|---|---|
| `created_at` | `DateTime(timezone=True)` | UTC timestamp on insert |
| `updated_at` | `DateTime(timezone=True)` | UTC timestamp on every write |
| `created_by` | `String(255)` | Actor who created the record |
| `updated_by` | `String(255)` | Actor who last modified the record |

Actor columns store plain string identifiers. The current values are:
- `"system"` — automated writes (e.g. seeding, migrations)
- `"anonymous"` — requests without an identified user when auth is disabled
- `"{username}"` — the `x-auth-user` header value when auth is enabled

These values are intentionally compatible with a future SSO user table. When a user table is introduced, `created_by`/`updated_by` may gain an optional FK relationship without requiring a column type change.

## Migration Naming Convention

Migration files follow the Alembic default: `{revision_id}_{slug}.py`.

Slug format: present-tense verb phrase describing the change:
- `add_config_template_table`
- `add_tool_id_index_to_override_layer`
- `drop_legacy_preset_file_column`
- `add_actor_column_to_version_entry`

## Alembic Workflow

```bash
# Create a new revision with autogenerate
make db-revision message="add config template table"

# Apply all pending migrations
make db-upgrade

# Roll back one step
make db-downgrade

# Check current migration state
cd backend && uv run alembic current

# View full history
cd backend && uv run alembic history
```

See `backend/alembic/README.md` for full reference.

## Local MySQL Setup

1. Start the MySQL container: `docker compose up mysql`
2. The container creates the `ai_config_wizard` database automatically.
3. Connection details for local development are in `.env.example`.
4. Copy `.env.example` to `.env` and adjust as needed.
5. For development outside Docker, set `DATABASE_HOST=127.0.0.1` (the container exposes port 3306 locally).

## Test Database Expectations

- Tests do not connect to MySQL by default.
- Unit tests use mocked sessions or in-memory SQLite where possible.
- Integration tests that require a live database use a separate test database.
- The test database name follows the pattern: `ai_config_wizard_test`.
- Test database settings are set via `TEST_DATABASE_URL` or equivalent environment variables.
- Tests must never connect to a production or developer database.
- The `conftest.py` in `backend/tests/` sets up an isolated config data directory and must also set up an isolated database session for DB-backed tests.

See `backend/tests/test_db_infrastructure.py` for the current test database setup.

## Deferred: SSO and User Table

SSO integration and a full user management system are explicitly out of scope for Phase 1.

The `created_by` and `updated_by` columns store string actor values that will be compatible with a future user table without requiring a schema migration.

When SSO is introduced (future phase):
1. A `users` table will be created with `id`, `username`, `email`, and SSO provider fields.
2. `created_by` and `updated_by` may gain optional foreign key references to `users.username`.
3. The existing string values (`"system"`, `"anonymous"`) will remain valid for automated writes.
4. No column type change will be needed.

## Deferred: Full RBAC Model

The current role model (`config_editor`, `audit_viewer`) is header-based and sufficient for Phase 1.

A database-backed RBAC model (roles table, user-role assignments, resource-level permissions) is deferred to a future phase.
