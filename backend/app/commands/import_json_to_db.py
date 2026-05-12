"""Ticket 16 — Unified JSON-to-database import command.

Usage
-----
    python -m app.commands.import_json_to_db [--dry-run] [--data-dir PATH]

Run order
---------
1. import_tools_and_languages — creates ``ai_tool`` and ``language`` rows
2. import_schema              — creates ``config_schema``, ``config_step``, ``config_field``
3. import_layers              — creates ``config_layer`` + all override rows

All three steps must succeed for the DB to be in a consistent state.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.import_ import (
    ImportResult,
    import_layers,
    import_schema,
    import_tools_and_languages,
)


# ---------------------------------------------------------------------------
# Default data directory
# ---------------------------------------------------------------------------

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "wizard_configs"


# ---------------------------------------------------------------------------
# Core orchestration (callable from tests or other code)
# ---------------------------------------------------------------------------


async def run_import(
    session: AsyncSession,
    data_dir: Path,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Run all import steps in order and return a combined result.

    Parameters
    ----------
    session:
        Async SQLAlchemy session.  The caller is responsible for
        commit / rollback.
    data_dir:
        Root wizard config directory.
    dry_run:
        When ``True``, compute what would change but do not write to the DB.
    """
    r1 = await import_tools_and_languages(session, data_dir, dry_run=dry_run)
    r2 = await import_schema(session, data_dir, dry_run=dry_run)
    r3 = await import_layers(session, data_dir, dry_run=dry_run)
    return r1.merge(r2).merge(r3)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import JSON wizard configs into the database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute changes without writing to the database.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_DEFAULT_DATA_DIR,
        help="Path to the wizard_configs directory.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="SQLAlchemy async database URL (overrides settings).",
    )
    args = parser.parse_args(argv)

    # Resolve DB URL
    if args.db_url:
        db_url = args.db_url
    else:
        try:
            from app.settings import get_settings  # type: ignore[import]
            db_url = get_settings().database.url
        except Exception:  # noqa: BLE001
            print(
                "ERROR: Could not read DATABASE_URL from settings. "
                "Pass --db-url or set the DATABASE_URL environment variable.",
                file=sys.stderr,
            )
            return 1

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    dry_label = " [DRY RUN]" if args.dry_run else ""
    print(f"Importing from {args.data_dir}{dry_label} ...")

    async with factory() as session:
        try:
            result = await run_import(session, args.data_dir, dry_run=args.dry_run)
            if not args.dry_run:
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    print(f"  created:   {result.created}")
    print(f"  updated:   {result.updated}")
    print(f"  unchanged: {result.unchanged}")
    print(f"  skipped:   {result.skipped}")
    print(f"  errors:    {len(result.errors)}")

    if result.errors:
        print("\nErrors:")
        for err in result.errors:
            print(f"  - {err}")
        return 1

    print("\nDone." if not args.dry_run else "\nDry run complete — no changes written.")
    await engine.dispose()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(_main()))
