"""Phase 4 tests — lifecycle, drafts, revisions, candidates.

Uses an isolated in-memory SQLite DB (named, shared, module-scoped).
All Phase 4 service functions are tested directly (unit-style integration).

Tests are organised by ticket area:
  - TestDraftLifecycle        — Tickets 2, 3, 5, 6, 7, 9, 10
  - TestLayerComparison       — Ticket 11
  - TestRevisionService       — Tickets 14, 15, 16
  - TestCandidateService      — Tickets 18, 19, 20, 21
  - TestPhase4Routes          — HTTP smoke tests via TestClient
"""
from __future__ import annotations

import os
from typing import Any, AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
import app.db.models  # noqa: F401 — registers all ORM models with Base.metadata
import app.services.config_loader_composable as _loader_mod

DATABASE_URL = (
    "sqlite+aiosqlite:///file:test_phase4_db"
    "?mode=memory&cache=shared&uri=true"
)

# ---------------------------------------------------------------------------
# Module-scoped engine / seeded DB
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
async def seed_db(factory):
    """Seed the in-memory DB with real config data before any tests run."""
    from app.commands.import_json_to_db import run_import

    data_dir = _loader_mod.DATA_DIR
    async with factory() as session:
        await run_import(session, data_dir)
        await session.commit()


# ---------------------------------------------------------------------------
# Helper — pick a known tool key from the seeded DB
# ---------------------------------------------------------------------------


async def _get_first_tool_key(session: AsyncSession) -> str:
    from sqlalchemy import select
    from app.db.models.tool import AITool

    res = await session.execute(select(AITool).where(AITool.is_active.is_(True)).limit(1))
    tool = res.scalar_one_or_none()
    assert tool is not None, "No active tool in seeded DB"
    return tool.tool_key


async def _get_first_language_key(session: AsyncSession) -> str:
    from sqlalchemy import select
    from app.db.models.language import Language

    res = await session.execute(select(Language).where(Language.is_active.is_(True)).limit(1))
    lang = res.scalar_one_or_none()
    assert lang is not None, "No active language in seeded DB"
    return lang.language_key


async def _get_active_tool_layer_id(session: AsyncSession, tool_key: str) -> int | None:
    from sqlalchemy import select
    from app.db.models.layer import ConfigLayer
    from app.db.models.tool import AITool

    tool_res = await session.execute(
        select(AITool).where(AITool.tool_key == tool_key).limit(1)
    )
    tool = tool_res.scalar_one_or_none()
    if not tool:
        return None

    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "tool",
            ConfigLayer.tool_id == tool.id,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    return layer.id if layer else None


# ---------------------------------------------------------------------------
# TestDraftLifecycle
# ---------------------------------------------------------------------------


class TestDraftLifecycle:
    async def test_create_draft_from_active(self, factory):
        """Ticket 3 — create_draft_from_active returns a draft layer dict."""
        from app.services.draft_service import create_draft_from_active

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            result = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="test_user",
                draft_name="Test Draft",
                draft_summary="Testing draft creation",
            )
            await session.commit()

        assert result["status"] == "draft"
        assert result["draft_name"] == "Test Draft"
        assert "id" in result

    async def test_create_draft_raises_for_unknown_tool(self, factory):
        """Ticket 3 — create_draft_from_active raises for non-existent target."""
        from app.services.draft_service import ActiveLayerNotFoundError, create_draft_from_active

        async with factory() as session:
            with pytest.raises(ActiveLayerNotFoundError):
                await create_draft_from_active(
                    session,
                    scope="tool",
                    target="nonexistent_tool_xyz",
                    actor="test_user",
                    draft_name="Bad Draft",
                )

    async def test_list_drafts(self, factory):
        """Ticket 10 — list_drafts returns at least the draft we just created."""
        from app.services.draft_service import list_drafts

        async with factory() as session:
            drafts = await list_drafts(session)

        assert isinstance(drafts, list)
        assert any(d["status"] == "draft" for d in drafts)

    async def test_list_drafts_filter_by_status(self, factory):
        """Ticket 10 — list_drafts can filter by status."""
        from app.services.draft_service import list_drafts

        async with factory() as session:
            drafts = await list_drafts(session, status="draft")

        assert all(d["status"] == "draft" for d in drafts)

    async def test_diff_draft_vs_source(self, factory):
        """Ticket 6 — diff_draft_vs_source returns expected shape."""
        from app.services.draft_service import create_draft_from_active, diff_draft_vs_source

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            draft = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="diff_user",
                draft_name="Diff Test Draft",
            )
            await session.commit()

        async with factory() as session:
            diff = await diff_draft_vs_source(session, draft["id"])

        assert "draft_layer_id" in diff
        assert "changes" in diff
        assert "change_count" in diff
        assert isinstance(diff["changes"], list)

    async def test_archive_draft(self, factory):
        """Ticket 9 — archive_draft sets status=archived."""
        from app.services.draft_service import archive_draft, create_draft_from_active

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            draft = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="archive_user",
                draft_name="To Be Archived",
            )
            await session.commit()

        async with factory() as session:
            result = await archive_draft(
                session, draft["id"], "archive_user", reason="No longer needed"
            )
            await session.commit()

        assert result["status"] == "archived"

    async def test_archive_already_archived_raises(self, factory):
        """Ticket 9 — archiving an archived draft raises DraftServiceError."""
        from app.services.draft_service import (
            DraftServiceError,
            archive_draft,
            create_draft_from_active,
        )

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            draft = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="double_archive_user",
                draft_name="Double Archive Test",
            )
            await session.commit()

        async with factory() as session:
            await archive_draft(session, draft["id"], "double_archive_user")
            await session.commit()

        async with factory() as session:
            with pytest.raises(DraftServiceError):
                await archive_draft(session, draft["id"], "double_archive_user")

    async def test_promote_draft(self, factory):
        """Ticket 7/8 — promote_draft returns promoted layer with status=active."""
        from app.services.draft_service import create_draft_from_active, promote_draft

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            draft = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="promote_user",
                draft_name="Promotion Test",
                draft_summary="Will be promoted",
            )
            await session.commit()

        async with factory() as session:
            result = await promote_draft(
                session, draft["id"], "promote_user", summary="Promoted by test"
            )
            await session.commit()

        assert result["promoted_layer"]["status"] == "active"
        assert result["promoted_layer"]["id"] == draft["id"]


# ---------------------------------------------------------------------------
# TestLayerComparison
# ---------------------------------------------------------------------------


class TestLayerComparison:
    async def test_compare_two_layers_same_type(self, factory):
        """Ticket 11 — compare_layers returns diff structure for two tool layers."""
        from app.services.draft_service import create_draft_from_active
        from app.services.layer_comparison import compare_layers

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            active_id = await _get_active_tool_layer_id(session, tool_key)
            if active_id is None:
                pytest.skip(f"No active layer for tool {tool_key!r}")

            draft = await create_draft_from_active(
                session,
                scope="tool",
                target=tool_key,
                actor="compare_user",
                draft_name="Compare Test",
            )
            await session.commit()

        async with factory() as session:
            result = await compare_layers(session, active_id, draft["id"])

        assert "changes" in result
        assert result["left_layer_id"] == active_id
        assert result["right_layer_id"] == draft["id"]

    async def test_compare_incompatible_types_raises(self, factory):
        """Ticket 11 — comparing layers of different types raises ComparisonError."""
        from sqlalchemy import select
        from app.db.models.layer import ConfigLayer
        from app.services.layer_comparison import ComparisonError, compare_layers

        async with factory() as session:
            tool_layer_res = await session.execute(
                select(ConfigLayer).where(
                    ConfigLayer.layer_type == "tool",
                    ConfigLayer.status == "active",
                ).limit(1)
            )
            tool_layer = tool_layer_res.scalar_one_or_none()

            lang_layer_res = await session.execute(
                select(ConfigLayer).where(
                    ConfigLayer.layer_type == "language",
                    ConfigLayer.status == "active",
                ).limit(1)
            )
            lang_layer = lang_layer_res.scalar_one_or_none()

            if not tool_layer or not lang_layer:
                pytest.skip("Need at least one tool and one language layer")

            with pytest.raises(ComparisonError):
                await compare_layers(session, tool_layer.id, lang_layer.id)


# ---------------------------------------------------------------------------
# TestRevisionService
# ---------------------------------------------------------------------------


class TestRevisionService:
    async def test_save_revision(self, factory):
        """Ticket 14 — save_revision creates a revision with values."""
        from app.services.revision_service import save_revision

        async with factory() as session:
            result = await save_revision(
                session,
                owner_actor="alice",
                name="My Test Revision",
                answers={"claude_md.tech_stack": "Python, FastAPI"},
                description="Test description",
            )
            await session.commit()

        assert result["owner_actor"] == "alice"
        assert result["name"] == "My Test Revision"
        assert result["status"] == "active"
        assert len(result["values"]) == 1

    async def test_save_revision_rejects_unknown_field(self, factory):
        """Ticket 14 — save_revision rejects field paths not in active schema."""
        from app.services.revision_service import RevisionServiceError, save_revision

        async with factory() as session:
            with pytest.raises(RevisionServiceError, match="does not exist"):
                await save_revision(
                    session,
                    owner_actor="bob",
                    name="Bad Revision",
                    answers={"this_field_does_not_exist_xyz": "value"},
                )

    async def test_list_revisions(self, factory):
        """Ticket 15 — list_revisions returns actor's own revisions."""
        from app.services.revision_service import list_revisions, save_revision

        async with factory() as session:
            await save_revision(
                session,
                owner_actor="list_user",
                name="Listed Revision",
                answers={"claude_md.tech_stack": "mature"},
            )
            await session.commit()

        async with factory() as session:
            results = await list_revisions(session, "list_user")

        assert len(results) >= 1
        assert all(r["owner_actor"] == "list_user" for r in results)

    async def test_get_revision(self, factory):
        """Ticket 15 — get_revision returns full revision with values."""
        from app.services.revision_service import get_revision, save_revision

        async with factory() as session:
            saved = await save_revision(
                session,
                owner_actor="get_user",
                name="Get Revision Test",
                answers={"claude_md.tech_stack": "brownfield"},
            )
            await session.commit()

        async with factory() as session:
            result = await get_revision(session, saved["id"], "get_user")

        assert result["id"] == saved["id"]
        assert result["values"][0]["field_path"] == "claude_md.tech_stack"

    async def test_get_revision_ownership_error(self, factory):
        """Ticket 15 — get_revision raises RevisionOwnershipError for wrong actor."""
        from app.services.revision_service import RevisionOwnershipError, get_revision, save_revision

        async with factory() as session:
            saved = await save_revision(
                session,
                owner_actor="owner_user",
                name="Private Revision",
                answers={"claude_md.tech_stack": "mature"},
            )
            await session.commit()

        async with factory() as session:
            with pytest.raises(RevisionOwnershipError):
                await get_revision(session, saved["id"], "other_user")

    async def test_archive_revision(self, factory):
        """Ticket 16 — archive_revision sets status=archived."""
        from app.services.revision_service import archive_revision, save_revision

        async with factory() as session:
            saved = await save_revision(
                session,
                owner_actor="archive_rev_user",
                name="To Archive",
                answers={"claude_md.tech_stack": "greenfield"},
            )
            await session.commit()

        async with factory() as session:
            result = await archive_revision(session, saved["id"], "archive_rev_user")
            await session.commit()

        assert result["status"] == "archived"

    async def test_archive_revision_already_archived_raises(self, factory):
        """Ticket 16 — double archive raises RevisionServiceError."""
        from app.services.revision_service import (
            RevisionServiceError,
            archive_revision,
            save_revision,
        )

        async with factory() as session:
            saved = await save_revision(
                session,
                owner_actor="double_archive_rev_user",
                name="Double Archive Rev",
                answers={"claude_md.tech_stack": "mature"},
            )
            await session.commit()

        async with factory() as session:
            await archive_revision(session, saved["id"], "double_archive_rev_user")
            await session.commit()

        async with factory() as session:
            with pytest.raises(RevisionServiceError, match="already archived"):
                await archive_revision(session, saved["id"], "double_archive_rev_user")

    async def test_archived_excluded_from_list_by_default(self, factory):
        """Ticket 16 — archived revisions excluded from list unless include_archived=True."""
        from app.services.revision_service import archive_revision, list_revisions, save_revision

        actor = "filter_archive_user"

        async with factory() as session:
            saved = await save_revision(
                session,
                owner_actor=actor,
                name="To Filter",
                answers={"claude_md.tech_stack": "greenfield"},
            )
            await session.commit()

        async with factory() as session:
            await archive_revision(session, saved["id"], actor)
            await session.commit()

        async with factory() as session:
            without = await list_revisions(session, actor, include_archived=False)
            with_archived = await list_revisions(session, actor, include_archived=True)

        assert not any(r["id"] == saved["id"] for r in without)
        assert any(r["id"] == saved["id"] for r in with_archived)


# ---------------------------------------------------------------------------
# TestCandidateService
# ---------------------------------------------------------------------------


class TestCandidateService:
    async def _create_revision(self, factory, actor: str, name: str) -> dict:
        from app.services.revision_service import save_revision

        async with factory() as session:
            result = await save_revision(
                session,
                owner_actor=actor,
                name=name,
                answers={"claude_md.tech_stack": "greenfield"},
            )
            await session.commit()
        return result

    async def test_submit_candidate(self, factory):
        """Ticket 18 — submit_candidate creates a TemplateCandidate."""
        from app.services.candidate_service import submit_candidate

        rev = await self._create_revision(factory, "submitter", "Submit Test Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            result = await submit_candidate(
                session,
                rev["id"],
                "submitter",
                "tool",
                "Test candidate summary",
                target_tool_key=tool_key,
            )
            await session.commit()

        assert result["status"] == "submitted"
        assert result["submitted_by"] == "submitter"

    async def test_submit_candidate_wrong_owner_raises(self, factory):
        """Ticket 18 — submit_candidate raises RevisionOwnershipError for wrong actor."""
        from app.services.candidate_service import submit_candidate
        from app.services.revision_service import RevisionOwnershipError

        rev = await self._create_revision(factory, "real_owner", "Ownership Test Rev")

        async with factory() as session:
            with pytest.raises(RevisionOwnershipError):
                await submit_candidate(
                    session,
                    rev["id"],
                    "wrong_user",
                    "tool",
                    "summary",
                )

    async def test_list_candidates(self, factory):
        """Ticket 19 — list_candidates returns submitted candidate."""
        from app.services.candidate_service import list_candidates, submit_candidate

        rev = await self._create_revision(factory, "list_cand_user", "List Cand Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            await submit_candidate(
                session,
                rev["id"],
                "list_cand_user",
                "tool",
                "For listing",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            candidates = await list_candidates(session, status="submitted")

        assert len(candidates) >= 1
        assert all(c["status"] == "submitted" for c in candidates)

    async def test_reject_candidate(self, factory):
        """Ticket 19 — reject_candidate sets status=rejected."""
        from app.services.candidate_service import reject_candidate, submit_candidate

        rev = await self._create_revision(factory, "reject_cand_user", "Reject Cand Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            candidate = await submit_candidate(
                session,
                rev["id"],
                "reject_cand_user",
                "tool",
                "Will be rejected",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            result = await reject_candidate(
                session, candidate["id"], "reviewer", review_notes="Not suitable"
            )
            await session.commit()

        assert result["status"] == "rejected"
        assert result["reviewed_by"] == "reviewer"

    async def test_reject_non_submitted_raises(self, factory):
        """Ticket 19 — rejecting already-rejected candidate raises CandidateStateError."""
        from app.services.candidate_service import (
            CandidateStateError,
            reject_candidate,
            submit_candidate,
        )

        rev = await self._create_revision(factory, "re_reject_user", "Re-reject Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            candidate = await submit_candidate(
                session, rev["id"], "re_reject_user", "tool", "summary",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            await reject_candidate(session, candidate["id"], "reviewer")
            await session.commit()

        async with factory() as session:
            with pytest.raises(CandidateStateError):
                await reject_candidate(session, candidate["id"], "reviewer")

    async def test_diff_candidate(self, factory):
        """Ticket 20 — diff_candidate returns comparison shape."""
        from app.services.candidate_service import diff_candidate, submit_candidate

        rev = await self._create_revision(factory, "diff_cand_user", "Diff Cand Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            candidate = await submit_candidate(
                session,
                rev["id"],
                "diff_cand_user",
                "tool",
                "Diff test",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            result = await diff_candidate(session, candidate["id"])

        assert "candidate_id" in result
        assert "changes" in result
        assert isinstance(result["changes"], list)

    async def test_accept_candidate_creates_draft(self, factory):
        """Ticket 21 — accept_candidate creates a draft layer."""
        from app.services.candidate_service import accept_candidate, submit_candidate

        rev = await self._create_revision(factory, "accept_cand_user", "Accept Cand Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            candidate = await submit_candidate(
                session,
                rev["id"],
                "accept_cand_user",
                "tool",
                "Accept test",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            result = await accept_candidate(
                session,
                candidate["id"],
                "reviewer",
                review_notes="Approved",
            )
            await session.commit()

        assert result["candidate"]["status"] == "accepted"
        assert result["draft_layer_id"] is not None

    async def test_withdraw_candidate(self, factory):
        """Ticket 19 — withdraw_candidate sets status=withdrawn."""
        from app.services.candidate_service import submit_candidate, withdraw_candidate

        rev = await self._create_revision(factory, "withdraw_user", "Withdraw Rev")

        async with factory() as session:
            tool_key = await _get_first_tool_key(session)
            candidate = await submit_candidate(
                session,
                rev["id"],
                "withdraw_user",
                "tool",
                "Will be withdrawn",
                target_tool_key=tool_key,
            )
            await session.commit()

        async with factory() as session:
            result = await withdraw_candidate(session, candidate["id"], "withdraw_user")
            await session.commit()

        assert result["status"] == "withdrawn"
