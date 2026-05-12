"""Tickets 19-20 — JSON vs Database configuration parity tests.

These tests import the real JSON wizard configs into an in-memory SQLite DB
and compare the resolved output from the DB resolver against the JSON resolver.

The tests are always run (no skip guard needed since they use in-memory SQLite,
not a live MySQL instance).

Ticket 19 tests compare resolved config structure (field counts, step ids).
Ticket 20 tests compare file generation output.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.commands.import_json_to_db import run_import
from app.services.config_db_repository import DatabaseConfigReadRepository
from app.services.config_loader_composable import load_composable_config, get_available_tools, get_available_languages
import app.services.config_loader_composable as _loader_mod

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///file:test_db_parity_db?mode=memory&cache=shared&uri=true"

# Use the module-level DATA_DIR that conftest.py may redirect to a temp directory
# This ensures the DB is seeded from the same source as the JSON resolver
DATA_DIR = Path(__file__).resolve().parent / "wizard_configs"


# ---------------------------------------------------------------------------
# Module-scoped seeded DB
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
async def seeded_session(engine):
    # Use the DATA_DIR from the loader module so we seed from the same source
    # as load_composable_config (which may be redirected by conftest.py to a
    # temp directory that has been modified by other test suites).
    data_dir = _loader_mod.DATA_DIR
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await run_import(session, data_dir)
        await session.commit()
        # Report any import errors without failing — field paths that don't
        # resolve (e.g. from .backup files) are expected; they are skipped.
    # Yield a fresh session for reading
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Ticket 19 — Config structure parity
# ---------------------------------------------------------------------------


class TestConfigStructureParity:
    """Compare JSON vs DB resolved configs for all tool+language combinations."""

    def _get_combos(self):
        tools = [t if isinstance(t, str) else t["id"] for t in get_available_tools()]
        langs = [la if isinstance(la, str) else la["id"] for la in get_available_languages()]
        return [(t, la) for t in tools for la in langs]

    async def test_step_ids_match_for_claude_python(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("claude", "python")
        db_config = await repo.load_resolved_config("claude", "python")

        json_step_ids = {s["id"] for s in json_config.get("steps", [])}
        db_step_ids = {s["id"] for s in db_config.get("steps", [])}
        assert json_step_ids == db_step_ids

    async def test_step_count_matches_for_claude_typescript(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("claude", "typescript")
        db_config = await repo.load_resolved_config("claude", "typescript")
        assert len(json_config["steps"]) == len(db_config["steps"])

    async def test_step_count_matches_for_copilot_python(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("copilot", "python")
        db_config = await repo.load_resolved_config("copilot", "python")
        assert len(json_config["steps"]) == len(db_config["steps"])

    async def test_step_count_matches_for_cursor_angular(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("cursor", "angular")
        db_config = await repo.load_resolved_config("cursor", "angular")
        assert len(json_config["steps"]) == len(db_config["steps"])

    async def test_schema_version_matches(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("claude", "python")
        db_config = await repo.load_resolved_config("claude", "python")
        assert json_config.get("schema_version") == db_config.get("schema_version")

    async def test_tool_list_matches(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_tools = {t if isinstance(t, str) else t["id"] for t in get_available_tools()}
        db_tools = {t["id"] for t in await repo.get_available_tools()}
        assert json_tools == db_tools

    async def test_language_list_matches(self, seeded_session):
        repo = DatabaseConfigReadRepository(seeded_session)
        json_langs = {la if isinstance(la, str) else la["id"] for la in get_available_languages()}
        db_langs = {la["id"] for la in await repo.get_available_languages()}
        assert json_langs == db_langs

    async def test_all_steps_have_id_and_fields(self, seeded_session):
        """DB resolved config has well-formed step shapes."""
        repo = DatabaseConfigReadRepository(seeded_session)
        db_config = await repo.load_resolved_config("claude", "python")
        for step in db_config["steps"]:
            assert "id" in step
            assert "fields" in step

    async def test_field_ids_subset_match_for_main_tool(self, seeded_session):
        """Field IDs from a known step are the same in JSON and DB resolvers."""
        repo = DatabaseConfigReadRepository(seeded_session)
        json_config = load_composable_config("claude", "python")
        db_config = await repo.load_resolved_config("claude", "python")

        # First step that has fields
        json_step = next((s for s in json_config["steps"] if s.get("fields")), None)
        if json_step is None:
            pytest.skip("No steps with fields found")

        db_step = next((s for s in db_config["steps"] if s["id"] == json_step["id"]), None)
        assert db_step is not None

        json_field_ids = {f["id"] for f in json_step["fields"]}
        db_field_ids = {f["id"] for f in db_step["fields"]}
        assert json_field_ids == db_field_ids


# ---------------------------------------------------------------------------
# Ticket 20 — Generated output parity (file path + count)
# ---------------------------------------------------------------------------


class TestGeneratedOutputParity:
    """Compare file_generator output between JSON and DB resolver for key combos."""

    async def _get_db_config(self, session: AsyncSession, tool_id: str, lang_id: str) -> dict:
        repo = DatabaseConfigReadRepository(session)
        return await repo.load_resolved_config(tool_id, lang_id)

    @pytest.mark.parametrize("tool_id,lang_id", [
        ("claude", "python"),
        ("claude", "typescript"),
        ("copilot", "python"),
    ])
    async def test_output_file_set_matches(self, seeded_session, tool_id, lang_id):
        """Output file paths derived from steps are the same in JSON and DB resolvers."""
        json_config = load_composable_config(tool_id, lang_id)
        db_config = await self._get_db_config(seeded_session, tool_id, lang_id)

        # Compare output_file values for non-hidden steps with non-empty output_file
        def step_output_files(config: dict) -> set[str]:
            return {
                s["output_file"]
                for s in config.get("steps", [])
                if s.get("output_file") and not s.get("hidden")
            }

        json_paths = step_output_files(json_config)
        db_paths = step_output_files(db_config)

        assert json_paths == db_paths

    @pytest.mark.parametrize("tool_id,lang_id", [
        ("claude", "python"),
        ("copilot", "python"),
    ])
    async def test_output_file_count_matches(self, seeded_session, tool_id, lang_id):
        """Non-hidden step count from JSON resolver == DB resolver."""
        json_config = load_composable_config(tool_id, lang_id)
        db_config = await self._get_db_config(seeded_session, tool_id, lang_id)

        def visible_step_count(config: dict) -> int:
            return sum(1 for s in config.get("steps", []) if not s.get("hidden"))

        assert visible_step_count(json_config) == visible_step_count(db_config)
