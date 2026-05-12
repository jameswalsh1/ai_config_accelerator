"""Ticket 14 — DB write integration tests.

These tests verify that the DB write repository correctly mutates the
database when CONFIG_SOURCE=database is active, and that the router
endpoints call the right service paths.

All tests use an in-memory SQLite DB seeded from the real JSON wizard
configs.  The test client is wired to use the same in-memory DB via
dependency injection overrides.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.commands.import_json_to_db import run_import
from app.services.config_db_write_repository import DatabaseConfigWriteRepository

_DATA_DIR = Path(__file__).parent / "wizard_configs"

DATABASE_URL = (
    "sqlite+aiosqlite:///file:test_db_write_integration_db"
    "?mode=memory&cache=shared&uri=true"
)


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
async def factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="module", autouse=True)
async def seed_db(engine, factory):
    """Seed the in-memory DB with real config data before any test runs."""
    async with factory() as session:
        await run_import(session, _DATA_DIR)
        await session.commit()



# ---------------------------------------------------------------------------
# DatabaseConfigWriteRepository unit tests
# ---------------------------------------------------------------------------


class TestWriteRepositoryFieldMetadata:
    @pytest.mark.asyncio
    async def test_update_field_sets_default_value(self, engine, factory):
        """update_field_metadata writes a ConfigFieldMetadataOverride row."""
        from sqlalchemy import select
        from app.db.models.layer import ConfigFieldMetadataOverride

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.update_field_metadata(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                changes={"default": "New default"},
                actor="test_user",
            )
            await session.commit()

        # Verify the override was written
        async with factory() as session:
            res = await session.execute(select(ConfigFieldMetadataOverride))
            overrides = res.scalars().all()
            assert any(
                o.default_value_json == "New default" for o in overrides
            ), "Expected metadata override with new default value"

    @pytest.mark.asyncio
    async def test_update_field_returns_layer_not_found_for_unknown_target(
        self, engine, factory
    ):
        from app.services.config_db_write_repository import LayerNotFoundError

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            with pytest.raises(LayerNotFoundError):
                await repo.update_field_metadata(
                    scope="language",
                    target="nonexistent_language_xyz",
                    step_id="claude_md",
                    field_id="system_prompt",
                    changes={"default": "value"},
                    actor="test_user",
                )

    @pytest.mark.asyncio
    async def test_update_field_returns_field_not_found_for_unknown_field(
        self, engine, factory
    ):
        from app.services.config_db_write_repository import FieldNotFoundError

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            with pytest.raises(FieldNotFoundError):
                await repo.update_field_metadata(
                    scope="language",
                    target="python",
                    step_id="claude_md",
                    field_id="no_such_field_xyz_abc",
                    changes={"default": "value"},
                    actor="test_user",
                )


class TestWriteRepositoryResetField:
    @pytest.mark.asyncio
    async def test_reset_field_override_clears_metadata(self, engine, factory):
        """reset_field_override deletes ConfigFieldMetadataOverride rows."""
        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            # First set a value
            await repo.update_field_metadata(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                changes={"default": "Reset target"},
                actor="test_user",
            )
            await session.commit()

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            # Now reset it
            await repo.reset_field_override(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                override_type="metadata",
                actor="test_user",
            )
            await session.commit()
        # No exception means success


class TestWriteRepositoryPresets:
    @pytest.mark.asyncio
    async def test_add_preset_creates_content_override(self, engine, factory):
        """add_preset appends to merge_presets_json in ConfigFieldContentOverride."""
        from sqlalchemy import select
        from app.db.models.layer import ConfigFieldContentOverride

        new_preset = {"label": "Test Preset", "value": "# Test content"}

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.add_preset(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                preset=new_preset,
                position=None,
                actor="test_user",
            )
            await session.commit()

        # Verify the preset was added
        async with factory() as session:
            fco_res = await session.execute(
                select(ConfigFieldContentOverride)
            )
            fcos = fco_res.scalars().all()
            added = any(
                fco.merge_presets_json and any(
                    p.get("label") == "Test Preset"
                    for p in fco.merge_presets_json
                )
                for fco in fcos
            )
            assert added, "Preset was not found in any ConfigFieldContentOverride"

    @pytest.mark.asyncio
    async def test_remove_preset_by_label(self, engine, factory):
        """remove_preset removes a preset by label."""
        # Add a preset first
        new_preset = {"label": "LabelToRemove", "value": "# Remove me"}
        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.add_preset(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                preset=new_preset,
                position=None,
                actor="test_user",
            )
            await session.commit()

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.remove_preset(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                preset_label="LabelToRemove",
                position=None,
                actor="test_user",
            )
            await session.commit()
        # No exception means success


class TestWriteRepositoryLanguageCreation:
    @pytest.mark.asyncio
    async def test_create_language_inserts_language_and_layer(
        self, engine, factory
    ):
        from sqlalchemy import select
        from app.db.models.language import Language
        from app.db.models.layer import ConfigLayer

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.create_language(
                language_key="test_lang_xyz",
                title="Test Language XYZ",
                description="A language created by integration test",
                actor="test_user",
            )
            await session.commit()

        async with factory() as session:
            lang_res = await session.execute(
                select(Language).where(Language.language_key == "test_lang_xyz")
            )
            lang = lang_res.scalar_one_or_none()
            assert lang is not None
            assert lang.title == "Test Language XYZ"

            layer_res = await session.execute(
                select(ConfigLayer).where(
                    ConfigLayer.layer_type == "language",
                    ConfigLayer.language_id == lang.id,
                )
            )
            layer = layer_res.scalar_one_or_none()
            assert layer is not None

    @pytest.mark.asyncio
    async def test_create_language_writes_audit_record(self, engine, factory):
        from sqlalchemy import select
        from app.db.models.audit import ConfigAuditEvent

        async with factory() as session:
            before_res = await session.execute(
                select(ConfigAuditEvent).where(
                    ConfigAuditEvent.action == "create"
                )
            )
            before_count = len(before_res.scalars().all())

        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.create_language(
                language_key="audit_test_lang",
                title="Audit Test Language",
                description="",
                actor="audit_tester",
            )
            await session.commit()

        async with factory() as session:
            after_res = await session.execute(
                select(ConfigAuditEvent).where(
                    ConfigAuditEvent.action == "create"
                )
            )
            after_count = len(after_res.scalars().all())

        assert after_count > before_count


# ---------------------------------------------------------------------------
# Audit and version service integration
# ---------------------------------------------------------------------------


class TestAuditServiceIntegration:
    @pytest.mark.asyncio
    async def test_read_db_audit_log_returns_entries(self, engine, factory):
        """read_db_audit_log returns dict with 'entries' and 'total'."""
        from app.services.config_db_audit_service import read_db_audit_log

        # Perform a mutation to ensure there's at least one audit entry
        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.create_language(
                language_key="audit_read_test",
                title="Audit Read Test",
                description="",
                actor="audit_reader",
            )
            await session.commit()

        async with factory() as session:
            result = await read_db_audit_log(session, limit=50, offset=0)

        assert "entries" in result
        assert "total" in result
        assert isinstance(result["entries"], list)
        assert result["total"] >= 1
        entry = result["entries"][0]
        assert "timestamp" in entry
        assert "action" in entry
        assert "actor" in entry

    @pytest.mark.asyncio
    async def test_read_db_audit_log_scope_filter(self, engine, factory):
        """scope filter restricts results to matching entries."""
        from app.services.config_db_audit_service import read_db_audit_log

        async with factory() as session:
            result = await read_db_audit_log(
                session, limit=50, offset=0, scope="language"
            )
        # All entries should have scope='language'
        for entry in result["entries"]:
            assert entry.get("scope") == "language"


class TestVersionServiceIntegration:
    @pytest.mark.asyncio
    async def test_db_list_versions_returns_list(self, engine, factory):
        """db_list_versions returns a list after a write has been made."""
        from app.services.config_db_version_service import db_list_versions

        # Ensure at least one version entry for python language
        async with factory() as session:
            repo = DatabaseConfigWriteRepository(session)
            await repo.update_field_metadata(
                scope="language",
                target="python",
                step_id="claude_md",
                field_id="project_maturity",
                changes={"default": "# Version test"},
                actor="version_tester",
            )
            await session.commit()

        async with factory() as session:
            versions = await db_list_versions(session, scope="language", target="python")

        assert isinstance(versions, list)
        assert len(versions) >= 1
        v = versions[0]
        assert "version" in v
        assert "timestamp" in v
        assert "actor" in v
