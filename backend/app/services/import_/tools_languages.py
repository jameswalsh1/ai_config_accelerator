"""Ticket 11 — JSON import service for AI tools and languages.

Reads:
  - ``{data_dir}/tools/{tool_id}.json``  → ``ai_tool`` rows
  - ``{data_dir}/languages/{language_id}.json`` → ``language`` rows

Strategy: idempotent upsert (select → insert or update).
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tool import AITool
from app.db.models.language import Language
from app.services.import_.result import ImportResult


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def _upsert_tool(
    session: AsyncSession,
    tool_key: str,
    title: str,
    description: str,
    dry_run: bool,
) -> str:
    """Insert or update a single AITool row. Returns 'created'|'updated'|'unchanged'."""
    result = await session.execute(
        select(AITool).where(AITool.tool_key == tool_key)
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        if not dry_run:
            session.add(AITool(tool_key=tool_key, title=title, description=description))
        return "created"

    changed = existing.title != title or existing.description != description
    if changed and not dry_run:
        existing.title = title
        existing.description = description
    return "updated" if changed else "unchanged"


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


async def _upsert_language(
    session: AsyncSession,
    language_key: str,
    title: str,
    description: str,
    dry_run: bool,
) -> str:
    """Insert or update a single Language row. Returns 'created'|'updated'|'unchanged'."""
    result = await session.execute(
        select(Language).where(Language.language_key == language_key)
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        if not dry_run:
            session.add(Language(language_key=language_key, title=title, description=description))
        return "created"

    changed = existing.title != title or existing.description != description
    if changed and not dry_run:
        existing.title = title
        existing.description = description
    return "updated" if changed else "unchanged"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def import_tools_and_languages(
    session: AsyncSession,
    data_dir: Path,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import all tool and language JSON files from *data_dir*.

    Parameters
    ----------
    session:
        Async SQLAlchemy session (caller is responsible for commit/rollback).
    data_dir:
        Root wizard config directory (e.g. ``app/data/wizard_configs/``).
    dry_run:
        When ``True``, compute what would change but do not write to the DB.
    """
    result = ImportResult()

    # --- Tools ---
    tools_dir = data_dir / "tools"
    if tools_dir.is_dir():
        for json_file in sorted(tools_dir.glob("*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
                tool_key: str = raw["tool_id"]
                tool_meta: dict = raw.get("tool_metadata", {})
                title: str = tool_meta.get("title", tool_key)
                description: str = tool_meta.get("description", "")
                outcome = await _upsert_tool(session, tool_key, title, description, dry_run)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"tools/{json_file.name}: {exc}")
                continue

            if outcome == "created":
                result.created += 1
            elif outcome == "updated":
                result.updated += 1
            else:
                result.unchanged += 1

    # --- Languages ---
    langs_dir = data_dir / "languages"
    if langs_dir.is_dir():
        for json_file in sorted(langs_dir.glob("*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
                lang_key: str = raw["language_id"]
                metadata: dict = raw.get("metadata", {})
                title = metadata.get("title", lang_key)
                description = metadata.get("description", "")
                outcome = await _upsert_language(session, lang_key, title, description, dry_run)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"languages/{json_file.name}: {exc}")
                continue

            if outcome == "created":
                result.created += 1
            elif outcome == "updated":
                result.updated += 1
            else:
                result.unchanged += 1

    if not dry_run:
        await session.flush()

    return result
