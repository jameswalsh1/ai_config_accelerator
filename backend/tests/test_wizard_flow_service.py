"""Tests for the Phase 5B wizard flow service.

The pure functions (apply_flow_to_config) are tested without a DB.
The async CRUD functions are tested using an in-memory SQLite database
via the SQLAlchemy async engine.
"""
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
import app.db.models  # noqa: F401 — ensures all models register with Base.metadata
from app.services.wizard_flow_service import (
    FlowNotFoundError,
    FlowOwnershipError,
    apply_flow_to_config,
    archive_flow,
    create_flow,
    get_flow,
    list_flows,
    set_default_flow,
    update_flow,
)


# ---------------------------------------------------------------------------
# In-memory SQLite fixtures (no TEST_DATABASE_URL required)
# ---------------------------------------------------------------------------

_DB_URL = "sqlite+aiosqlite:///file:test_flow_service?mode=memory&cache=shared&uri=true"


@pytest_asyncio.fixture(scope="module")
async def db_engine():
    engine = create_async_engine(_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


# ---------------------------------------------------------------------------
# apply_flow_to_config — pure function, no DB needed
# ---------------------------------------------------------------------------


class TestApplyFlowToConfig:
    def _config(self, step_ids: list[str]) -> dict[str, Any]:
        return {
            "id": "my-config",
            "title": "Test",
            "steps": [{"id": k, "title": k.title(), "fields": []} for k in step_ids],
        }

    def _flow_steps(self, keys: list[str], enabled: list[bool] | None = None) -> list[dict[str, Any]]:
        enabled = enabled or [True] * len(keys)
        return [
            {"step_key": k, "is_enabled": e, "custom_title": None, "custom_description": None}
            for k, e in zip(keys, enabled)
        ]

    def test_reorders_steps(self):
        config = self._config(["a", "b", "c"])
        flow_steps = self._flow_steps(["c", "a", "b"])
        result = apply_flow_to_config(config, flow_steps)
        assert [s["id"] for s in result["steps"]] == ["c", "a", "b"]

    def test_excludes_disabled_steps(self):
        config = self._config(["a", "b", "c"])
        flow_steps = self._flow_steps(["a", "b", "c"], enabled=[True, False, True])
        result = apply_flow_to_config(config, flow_steps)
        assert [s["id"] for s in result["steps"]] == ["a", "c"]

    def test_skips_missing_step_keys(self):
        config = self._config(["a", "b"])
        flow_steps = self._flow_steps(["a", "x", "b"])  # "x" not in config
        result = apply_flow_to_config(config, flow_steps)
        assert [s["id"] for s in result["steps"]] == ["a", "b"]

    def test_excludes_config_steps_not_in_flow(self):
        config = self._config(["a", "b", "c"])
        flow_steps = self._flow_steps(["a", "b"])  # "c" omitted
        result = apply_flow_to_config(config, flow_steps)
        assert [s["id"] for s in result["steps"]] == ["a", "b"]

    def test_custom_title_applied(self):
        config = self._config(["a"])
        flow_steps = [{"step_key": "a", "is_enabled": True, "custom_title": "My Title", "custom_description": None}]
        result = apply_flow_to_config(config, flow_steps)
        assert result["steps"][0]["title"] == "My Title"

    def test_custom_description_applied(self):
        config = self._config(["a"])
        flow_steps = [{"step_key": "a", "is_enabled": True, "custom_title": None, "custom_description": "My Desc"}]
        result = apply_flow_to_config(config, flow_steps)
        assert result["steps"][0]["description"] == "My Desc"

    def test_original_config_not_mutated(self):
        config = self._config(["a", "b"])
        original_step_count = len(config["steps"])
        flow_steps = self._flow_steps(["a"])
        apply_flow_to_config(config, flow_steps)
        assert len(config["steps"]) == original_step_count

    def test_empty_flow_steps_returns_empty_steps(self):
        config = self._config(["a", "b"])
        result = apply_flow_to_config(config, [])
        assert result["steps"] == []

    def test_non_step_keys_are_preserved(self):
        config = {**self._config(["a"]), "extra_key": "extra_value"}
        result = apply_flow_to_config(config, self._flow_steps(["a"]))
        assert result["extra_key"] == "extra_value"


# ---------------------------------------------------------------------------
# Async CRUD tests (in-memory SQLite)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFlowCRUD:
    async def test_create_flow_no_schema(self, session: AsyncSession):
        """create_flow raises FlowServiceError when no active schema exists."""
        from app.services.wizard_flow_service import FlowServiceError
        with pytest.raises(FlowServiceError, match="No active schema"):
            await create_flow(session, owner_actor="alice", name="My Flow")

    async def test_list_flows_empty(self, session: AsyncSession):
        result = await list_flows(session, owner_actor="alice")
        assert result == []

    async def test_get_flow_not_found(self, session: AsyncSession):
        with pytest.raises(FlowNotFoundError):
            await get_flow(session, flow_id=9999, owner_actor="alice")

    async def test_ownership_error(self, session: AsyncSession):
        """Getting a flow owned by another actor raises FlowOwnershipError."""
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        flow = WizardFlow(
            owner_actor="bob",
            name="Bob's Flow",
            is_default=False,
            status="active",
            created_by="bob",
            updated_by="bob",
            created_at=now,
            updated_at=now,
        )
        session.add(flow)
        await session.flush()

        with pytest.raises(FlowOwnershipError):
            await get_flow(session, flow_id=flow.id, owner_actor="alice")

    async def test_archive_flow(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        flow = WizardFlow(
            owner_actor="alice",
            name="To Archive",
            is_default=False,
            status="active",
            created_by="alice",
            updated_by="alice",
            created_at=now,
            updated_at=now,
        )
        session.add(flow)
        await session.flush()

        result = await archive_flow(session, flow.id, "alice")
        assert result["status"] == "archived"
        assert result["is_default"] is False

    async def test_archive_flow_not_found(self, session: AsyncSession):
        with pytest.raises(FlowNotFoundError):
            await archive_flow(session, flow_id=9999, owner_actor="alice")

    async def test_set_default_flow(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        def _make(name: str) -> WizardFlow:
            return WizardFlow(
                owner_actor="carol",
                name=name,
                is_default=False,
                status="active",
                created_by="carol",
                updated_by="carol",
                created_at=now,
                updated_at=now,
            )

        flow1 = _make("Flow 1")
        flow2 = _make("Flow 2")
        session.add_all([flow1, flow2])
        await session.flush()

        # Set flow1 as default
        result = await set_default_flow(session, flow1.id, "carol")
        assert result["is_default"] is True

        # Set flow2 as default — flow1 should lose default status
        await set_default_flow(session, flow2.id, "carol")
        await session.refresh(flow1)
        assert flow1.is_default is False

    async def test_set_default_wrong_owner(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        flow = WizardFlow(
            owner_actor="dave",
            name="Dave's Flow",
            is_default=False,
            status="active",
            created_by="dave",
            updated_by="dave",
            created_at=now,
            updated_at=now,
        )
        session.add(flow)
        await session.flush()

        with pytest.raises(FlowOwnershipError):
            await set_default_flow(session, flow.id, "eve")

    async def test_update_flow_name(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        flow = WizardFlow(
            owner_actor="frank",
            name="Original",
            is_default=False,
            status="active",
            created_by="frank",
            updated_by="frank",
            created_at=now,
            updated_at=now,
        )
        session.add(flow)
        await session.flush()

        result = await update_flow(session, flow.id, "frank", name="Updated")
        assert result["name"] == "Updated"

    async def test_list_flows_excludes_archived_by_default(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        actor = "grace"
        active = WizardFlow(
            owner_actor=actor, name="Active", is_default=False, status="active",
            created_by=actor, updated_by=actor, created_at=now, updated_at=now,
        )
        archived = WizardFlow(
            owner_actor=actor, name="Archived", is_default=False, status="archived",
            created_by=actor, updated_by=actor, created_at=now, updated_at=now,
        )
        session.add_all([active, archived])
        await session.flush()

        result = await list_flows(session, owner_actor=actor)
        names = [f["name"] for f in result]
        assert "Active" in names
        assert "Archived" not in names

    async def test_list_flows_includes_archived_when_requested(self, session: AsyncSession):
        from app.db.models.flow import WizardFlow
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        actor = "henry"
        active = WizardFlow(
            owner_actor=actor, name="Active2", is_default=False, status="active",
            created_by=actor, updated_by=actor, created_at=now, updated_at=now,
        )
        archived = WizardFlow(
            owner_actor=actor, name="Archived2", is_default=False, status="archived",
            created_by=actor, updated_by=actor, created_at=now, updated_at=now,
        )
        session.add_all([active, archived])
        await session.flush()

        result = await list_flows(session, owner_actor=actor, include_archived=True)
        names = [f["name"] for f in result]
        assert "Active2" in names
        assert "Archived2" in names
