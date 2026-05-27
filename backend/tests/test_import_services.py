"""Tests for Phase 2 Tickets 11–16 — JSON import services.

Uses an in-memory SQLite DB (aiosqlite) seeded with minimal fixture data
so tests are fast and self-contained.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.tool import AITool
from app.db.models.language import Language
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.layer import ConfigLayer, ConfigStepOverride, ConfigFieldMetadataOverride, ConfigFieldContentOverride
from app.services.import_.result import ImportResult
from app.services.import_.tools_languages import import_tools_and_languages
from app.services.import_.schema import import_schema
from app.services.import_.layers import import_layers
from app.commands.import_json_to_db import run_import

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///file:test_import_services_db?mode=memory&cache=shared&uri=true"
NOW = datetime.now(tz=timezone.utc)


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


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


def _write_tool(tmp: Path, tool_id: str, title: str, desc: str = "") -> None:
    (tmp / "tools").mkdir(exist_ok=True)
    (tmp / "tools" / f"{tool_id}.json").write_text(json.dumps({
        "tool_id": tool_id,
        "tool_metadata": {"title": title, "description": desc},
        "version": "1.0",
        "applies_to": {"tools": [tool_id]},
        "metadata_overrides": [],
        "field_overrides": [],
        "step_overrides": [],
    }))


def _write_language(tmp: Path, lang_id: str, title: str, desc: str = "") -> None:
    (tmp / "languages").mkdir(exist_ok=True)
    (tmp / "languages" / f"{lang_id}.json").write_text(json.dumps({
        "language_id": lang_id,
        "version": "1.0",
        "metadata": {"title": title, "description": desc},
        "applies_to": {"languages": [lang_id]},
        "field_overrides": [],
        "metadata_overrides": [],
        "step_overrides": [],
    }))


def _write_schema(tmp: Path) -> None:
    (tmp / "schema.json").write_text(json.dumps({
        "schema_version": "2.0",
        "description": "Test schema",
        "steps": [
            {
                "id": "lang_step",
                "title": "Language",
                "output_file": "lang.md",
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
                        "id": "rules",
                        "type": "repeatable_group",
                        "label": "Rules",
                        "fields": [
                            {"id": "rule_file_name", "type": "text", "label": "Rule File Name"},
                        ],
                    },
                ],
            },
            {
                "id": "coding_step",
                "title": "Coding Standards",
                "output_file": "coding.md",
                "fields": [
                    {
                        "id": "conventions",
                        "type": "textarea",
                        "label": "Conventions",
                        "presets": [{"label": "PEP 8", "value": "pep8"}],
                    }
                ],
            },
        ],
    }))


# ---------------------------------------------------------------------------
# Ticket 11 — Tools and languages import
# ---------------------------------------------------------------------------


class TestImportToolsAndLanguages:
    async def test_creates_tools(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "claude", "Claude Code")
            _write_tool(tmp, "copilot", "GitHub Copilot")
            result = await import_tools_and_languages(session, tmp)
            assert result.created == 2
            assert result.errors == []

    async def test_creates_languages(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_language(tmp, "python", "Python", "Python 3")
            _write_language(tmp, "typescript", "TypeScript")
            result = await import_tools_and_languages(session, tmp)
            assert result.created == 2

    async def test_idempotent_second_run_unchanged(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "cursor_idem", "Cursor")
            # First run
            await import_tools_and_languages(session, tmp)
            await session.flush()
            # Second run
            result = await import_tools_and_languages(session, tmp)
            assert result.unchanged == 1
            assert result.created == 0

    async def test_update_on_title_change(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "update_tool", "Old Title")
            await import_tools_and_languages(session, tmp)
            await session.flush()
            # Update title
            _write_tool(tmp, "update_tool", "New Title")
            result = await import_tools_and_languages(session, tmp)
            assert result.updated == 1

    async def test_dry_run_does_not_write(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "dry_run_tool_import", "DRY")
            result = await import_tools_and_languages(session, tmp, dry_run=True)
            assert result.created == 1  # reported, but not written
            # Verify not in DB
            res = await session.execute(select(AITool).where(AITool.tool_key == "dry_run_tool_import"))
            assert res.scalar_one_or_none() is None

    async def test_missing_tool_id_skips_with_error(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "tools").mkdir()
            # Missing tool_id key
            (tmp / "tools" / "bad.json").write_text(json.dumps({"tool_metadata": {"title": "Bad"}}))
            result = await import_tools_and_languages(session, tmp)
            assert len(result.errors) == 1

    async def test_empty_dirs_no_error(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            result = await import_tools_and_languages(session, tmp)
            assert result.created == 0
            assert result.errors == []


# ---------------------------------------------------------------------------
# Ticket 12 — Schema import
# ---------------------------------------------------------------------------


class TestImportSchema:
    async def test_creates_schema_steps_fields(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            result = await import_schema(session, tmp)
            assert result.errors == []
            # 1 schema + 2 steps + 3 fields (language, rules, rule_file_name) + 1 conventions
            assert result.created >= 7

    async def test_schema_row_created(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            await import_schema(session, tmp)
            await session.flush()
            res = await session.execute(select(ConfigSchema).where(ConfigSchema.schema_version == "2.0"))
            schema = res.scalar_one_or_none()
            assert schema is not None
            assert schema.status == "active"

    async def test_nested_field_imported(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            await import_schema(session, tmp)
            await session.flush()
            res = await session.execute(
                select(ConfigField).where(ConfigField.field_path == "lang_step.rules.rule_file_name")
            )
            field = res.scalar_one_or_none()
            assert field is not None
            assert field.parent_field_id is not None

    async def test_idempotent_second_run(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            r1 = await import_schema(session, tmp)
            await session.flush()
            r2 = await import_schema(session, tmp)
            assert r2.created == 0
            assert r2.unchanged > 0

    async def test_schema_not_found_returns_error(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            result = await import_schema(session, tmp)
            assert len(result.errors) == 1

    async def test_step_position_set(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            await import_schema(session, tmp)
            await session.flush()
            res = await session.execute(select(ConfigStep).where(ConfigStep.step_key == "coding_step"))
            step = res.scalar_one_or_none()
            assert step is not None
            assert step.position == 1


# ---------------------------------------------------------------------------
# Ticket 13/14 — Layer import
# ---------------------------------------------------------------------------


class TestImportLayers:
    async def _seed_prerequisites(self, session, tmp: Path) -> None:
        """Seed tools, languages, and schema into DB."""
        _write_tool(tmp, "claude", "Claude Code")
        _write_language(tmp, "python", "Python")
        _write_schema(tmp)
        await import_tools_and_languages(session, tmp)
        await import_schema(session, tmp)
        await session.flush()

    async def test_tool_layer_created(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            await self._seed_prerequisites(session, tmp)
            result = await import_layers(session, tmp)
            assert result.errors == []
            res = await session.execute(
                select(ConfigLayer).where(ConfigLayer.layer_key == "tool:claude")
            )
            layer = res.scalar_one_or_none()
            assert layer is not None
            assert layer.layer_type == "tool"

    async def test_language_layer_created(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            await self._seed_prerequisites(session, tmp)
            result = await import_layers(session, tmp)
            assert result.errors == []
            res = await session.execute(
                select(ConfigLayer).where(ConfigLayer.layer_key == "language:python")
            )
            layer = res.scalar_one_or_none()
            assert layer is not None

    async def test_step_overrides_imported(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "step_ovr_tool", "Step OVR Tool")
            _write_schema(tmp)
            await import_tools_and_languages(session, tmp)
            await import_schema(session, tmp)
            await session.flush()
            # Add step override to tool json
            tool_json = {
                "tool_id": "step_ovr_tool",
                "tool_metadata": {"title": "Step OVR Tool"},
                "version": "1.0",
                "applies_to": {},
                "metadata_overrides": [],
                "field_overrides": [],
                "step_overrides": [{"step_id": "lang_step", "hidden": True}],
            }
            (tmp / "tools" / "step_ovr_tool.json").write_text(json.dumps(tool_json))
            result = await import_layers(session, tmp)
            assert result.errors == []

            # Verify step override row exists
            res = await session.execute(select(ConfigLayer).where(ConfigLayer.layer_key == "tool:step_ovr_tool"))
            layer = res.scalar_one_or_none()
            assert layer is not None
            ovr_res = await session.execute(
                select(ConfigStepOverride).where(ConfigStepOverride.layer_id == layer.id)
            )
            overrides = ovr_res.scalars().all()
            assert len(overrides) == 1
            assert overrides[0].hidden is True

    async def test_field_metadata_override_imported(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            _write_language(tmp, "meta_lang", "Meta Language")
            await import_tools_and_languages(session, tmp)
            await import_schema(session, tmp)
            await session.flush()
            # Language with metadata override
            lang_json = {
                "language_id": "meta_lang",
                "version": "1.0",
                "metadata": {"title": "Meta Language"},
                "applies_to": {},
                "field_overrides": [],
                "metadata_overrides": [
                    {"field_id": "lang_step.language", "default": "python"}
                ],
                "step_overrides": [],
            }
            (tmp / "languages" / "meta_lang.json").write_text(json.dumps(lang_json))
            result = await import_layers(session, tmp)
            assert result.errors == []

            res = await session.execute(select(ConfigLayer).where(ConfigLayer.layer_key == "language:meta_lang"))
            layer = res.scalar_one_or_none()
            assert layer is not None
            ovr_res = await session.execute(
                select(ConfigFieldMetadataOverride).where(ConfigFieldMetadataOverride.layer_id == layer.id)
            )
            overrides = ovr_res.scalars().all()
            assert len(overrides) == 1
            assert overrides[0].default_value_json == "python"

    async def test_field_content_override_imported(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            _write_language(tmp, "content_lang", "Content Language")
            await import_tools_and_languages(session, tmp)
            await import_schema(session, tmp)
            await session.flush()
            lang_json = {
                "language_id": "content_lang",
                "version": "1.0",
                "metadata": {"title": "Content Language"},
                "applies_to": {},
                "field_overrides": [
                    {
                        "field_id": "coding_step.conventions",
                        "merge_presets": [{"label": "PEP 8", "value": "pep8"}],
                        "merge_mode": "append",
                    }
                ],
                "metadata_overrides": [],
                "step_overrides": [],
            }
            (tmp / "languages" / "content_lang.json").write_text(json.dumps(lang_json))
            result = await import_layers(session, tmp)
            assert result.errors == []

            res = await session.execute(select(ConfigLayer).where(ConfigLayer.layer_key == "language:content_lang"))
            layer = res.scalar_one_or_none()
            ovr_res = await session.execute(
                select(ConfigFieldContentOverride).where(ConfigFieldContentOverride.layer_id == layer.id)
            )
            overrides = ovr_res.scalars().all()
            assert len(overrides) == 1

    async def test_unknown_field_records_error(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_schema(tmp)
            _write_language(tmp, "bad_ref_lang", "Bad Ref")
            await import_tools_and_languages(session, tmp)
            await import_schema(session, tmp)
            await session.flush()
            lang_json = {
                "language_id": "bad_ref_lang",
                "version": "1.0",
                "metadata": {"title": "Bad Ref"},
                "applies_to": {},
                "metadata_overrides": [
                    {"field_id": "nonexistent_step.nonexistent_field", "default": "x"}
                ],
                "field_overrides": [],
                "step_overrides": [],
            }
            (tmp / "languages" / "bad_ref_lang.json").write_text(json.dumps(lang_json))
            result = await import_layers(session, tmp)
            assert len(result.errors) == 1

    async def test_no_schema_returns_error(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            result = await import_layers(session, tmp)
            assert len(result.errors) == 1

    async def test_layer_idempotent(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            await self._seed_prerequisites(session, tmp)
            r1 = await import_layers(session, tmp)
            await session.flush()
            r2 = await import_layers(session, tmp)
            # Second run: layers should be unchanged, no extra layers created
            assert r2.created == 0


# ---------------------------------------------------------------------------
# Ticket 16 — run_import orchestration
# ---------------------------------------------------------------------------


class TestRunImport:
    async def test_full_import_succeeds(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "full_claude", "Claude")
            _write_language(tmp, "full_python", "Python")
            _write_schema(tmp)
            result = await run_import(session, tmp)
            assert result.errors == []
            assert result.created > 0

    async def test_import_result_merge(self):
        r1 = ImportResult(created=2, updated=1)
        r2 = ImportResult(created=3, errors=["e1"])
        merged = r1.merge(r2)
        assert merged.created == 5
        assert merged.updated == 1
        assert merged.errors == ["e1"]

    async def test_dry_run_no_db_writes(self, session):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_tool(tmp, "dry_full_tool", "Dry Full")
            _write_schema(tmp)
            result = await run_import(session, tmp, dry_run=True)
            assert result.created > 0
            # Tool not actually in DB
            res = await session.execute(select(AITool).where(AITool.tool_key == "dry_full_tool"))
            assert res.scalar_one_or_none() is None
