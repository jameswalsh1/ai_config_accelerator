## Alembic Migrations

### Create a new revision
```
make db-revision message="describe what changed"
# or directly:
cd backend && uv run alembic revision --autogenerate -m "describe what changed"
```

### Apply all pending migrations
```
make db-upgrade
# or directly:
cd backend && uv run alembic upgrade head
```

### Roll back one migration step
```
make db-downgrade
# or directly:
cd backend && uv run alembic downgrade -1
```

### View current migration state
```
cd backend && uv run alembic current
cd backend && uv run alembic history
```

---

### How it works

The `env.py` in this directory reads the database URL from the application's
`DatabaseSettings` (loaded from environment variables), so no credentials are
stored in version control.

Set `DATABASE_URL` in your local environment or in a `.env` file before
running any Alembic command.  See `.env.example` at the repo root.

All ORM models must inherit from `app.db.base.Base` and must be importable
from `alembic/env.py` for autogenerate to discover them.  Add import statements
near the top of `env.py` as new models are introduced.

---

### Naming convention

Migration files are named `{revision_id}_{slug}.py`, e.g.
`a3f1b2c4d5e6_add_config_template_table.py`.

Use present-tense verb phrases that describe the change:
- `add_config_template_table`
- `add_override_layer_enum_column`
- `drop_legacy_preset_file_column`
