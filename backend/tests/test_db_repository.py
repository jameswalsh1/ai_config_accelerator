"""Tests for Phase 2 Tickets 17-18 — DB read repository and DB-backed resolution.

All tests use in-memory SQLite (aiosqlite) and seed data via the import services.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.tool import AITool
from app.db.models.language import Language
from app.db.models.schema import ConfigSchema
from app.services.config_db_repository import DatabaseConfigReadRepository
from app.commands.import_json_to_db import run_import

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///file:test_db_repository_db?mode=memory&cache=shared&uri=true"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine(DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture(scope="module")
async def seeded_data_dir():
    """Create a minimal wizard_configs directory and return the path.

    Scoped to module so data is only written once.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        (tmp / "tools").mkdir()
        (tmp / "languages").mkdir()

        # Tool: claude with a step override
        (tmp / "tools" / "claude.json").write_text(json.dumps({
            "tool_id": "claude",
            "tool_metadata": {"title": "Claude Code", "description": "Anthropic Claude"},
            "version": "1.0",
            "applies_to": {"tools": ["claude"]},
            "metadata_overrides": [],
            "field_overrides": [],
            "step_overrides": [{"step_id": "hidden_step", "hidden": True}],
        }))

        # Language: python with a field metadata override
        (tmp / "languages" / "python.json").write_text(json.dumps({
            "language_id": "python",
            "version": "1.0",
            "metadata": {"title": "Python", "description": "Python 3"},
            "applies_to": {"languages": ["python"]},
            "metadata_overrides": [
                {"field_id": "main_step.language", "default": "python"}
            ],
            "field_overrides": [
                {
                    "field_id": "main_step.conventions",
                    "merge_presets": [{"label": "PEP 8", "value": "pep8"}],
                    "merge_mode": "append",
                }
            ],
            "step_overrides": [],
        }))

        # Schema
        (tmp / "schema.json").write_text(json.dumps({
            "schema_version": "2.0",
            "description": "Test schema",
            "steps": [
                {
                    "id": "main_step",
                    "title": "Main Step",
                    "output_file": "main.md",
                    "fields": [
                        {
                            "id": "language",
                            "type": "select",
                            "label": "Language",
                            "required": True,
                            "default": "typescript",
                            "options": [{"value": "ts", "label": "TypeScript"}],
                        },
                        {
                            "id": "conventions",
                            "type": "textarea",
                            "label": "Conventions",
                            "presets": [{"label": "Standard", "value": "std"}],
                        },
                    ],
                },
                {
                    "id": "hidden_step",
                    "title": "Hidden Step",
                    "output_file": "hidden.md",
                    "fields": [],
                },
            ],
        }))

        yield tmp


@pytest.fixture(scope="module")
async def populated_session(engine, seeded_data_dir):
    """Session with data imported from seeded_data_dir."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await run_import(session, seeded_data_dir)
        assert result.errors == [], f"Import errors: {result.errors}"
        await session.commit()
    # Return a fresh session for tests
    async with factory() as session:
        yield session


@pytest.fixture
async def repo(populated_session) -> DatabaseConfigReadRepository:
    return DatabaseConfigReadRepository(populated_session)


# ---------------------------------------------------------------------------
# Ticket 17 — DatabaseConfigReadRepository
# ---------------------------------------------------------------------------


class TestDatabaseConfigReadRepository:
    async def test_get_available_tools(self, repo):
        tools = await repo.get_available_tools()
        assert any(t["id"] == "claude" for t in tools)

    async def test_get_available_languages(self, repo):
        langs = await repo.get_available_languages()
        assert any(la["id"] == "python" for la in langs)

    async def test_tools_have_expected_fields(self, repo):
        tools = await repo.get_available_tools()
        for t in tools:
            assert "id" in t
            assert "title" in t

    async def test_languages_have_expected_fields(self, repo):
        langs = await repo.get_available_languages()
        for la in langs:
            assert "id" in la
            assert "title" in la

    async def test_load_resolved_config_returns_dict(self, repo):
        config = await repo.load_resolved_config("claude", "python")
        assert isinstance(config, dict)

    async def test_resolved_config_has_schema_version(self, repo):
        config = await repo.load_resolved_config("claude", "python")
        assert config["schema_version"] == "2.0"

    async def test_resolved_config_has_steps(self, repo):
        config = await repo.load_resolved_config("claude", "python")
        assert "steps" in config
        assert len(config["steps"]) > 0

    async def test_step_override_hidden_applied(self, repo):
        config = await repo.load_resolved_config("claude", "python")
        steps_by_id = {s["id"]: s for s in config["steps"]}
        assert steps_by_id["hidden_step"]["hidden"] is True

    async def test_field_metadata_override_applied(self, repo):
        """Language override sets default of language field to 'python'."""
        config = await repo.load_resolved_config("claude", "python")
        steps_by_id = {s["id"]: s for s in config["steps"]}
        fields_by_id = {f["id"]: f for f in steps_by_id["main_step"]["fields"]}
        lang_field = fields_by_id["language"]
        assert lang_field["default"] == "python"

    async def test_field_content_override_applied(self, repo):
        """Language override merges presets into conventions field."""
        config = await repo.load_resolved_config("claude", "python")
        steps_by_id = {s["id"]: s for s in config["steps"]}
        fields_by_id = {f["id"]: f for f in steps_by_id["main_step"]["fields"]}
        conv_field = fields_by_id["conventions"]
        preset_labels = [p["label"] for p in (conv_field.get("presets") or [])]
        assert "PEP 8" in preset_labels

    async def test_unknown_tool_resolves_without_tool_layer(self, repo):
        """Resolving with an unknown tool should still return schema-only config."""
        config = await repo.load_resolved_config("unknown_tool", "python")
        assert "steps" in config

    async def test_unknown_language_resolves_without_lang_layer(self, repo):
        config = await repo.load_resolved_config("claude", "unknown_lang")
        assert "steps" in config

    async def test_no_active_schema_raises(self):
        """When no active schema exists, load_resolved_config raises RuntimeError."""
        # Create an isolated DB with no schema
        eng = create_async_engine(
            "sqlite+aiosqlite:///file:test_no_schema_isolated?mode=memory&cache=shared&uri=true", echo=False
        )
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            repo = DatabaseConfigReadRepository(s)
            with pytest.raises(RuntimeError, match="No active config schema"):
                await repo.load_resolved_config("claude", "python")
        await eng.dispose()
