"""Ticket 12 — Export database config back to JSON files.

Reconstructs the canonical JSON file structure from the live database and
writes it to the output directory.

Usage
-----
    python -m app.commands.export_config_db_to_json [--output-dir PATH] [--dry-run] [--force]

Options
-------
``--output-dir PATH``
    Destination directory for exported JSON files.
    Defaults to ``backend/app/data/wizard_configs``.
``--dry-run``
    Print what would be exported without writing any files.
``--force``
    Overwrite existing files without prompting.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.config_db_exporter import export_all


_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "tests" / "wizard_configs"


async def run_export(
    session: AsyncSession,
    output_dir: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, list[str]]:
    """Export all DB config to ``output_dir``.

    Parameters
    ----------
    session:
        Async SQLAlchemy session (read-only; no commits are made).
    output_dir:
        Root directory under which files will be written.
    dry_run:
        If ``True``, compute exports but do not write any files.
    force:
        If ``True``, overwrite existing files without error.

    Returns
    -------
    dict with keys ``"written"``, ``"skipped"``, ``"errors"``.
    """
    exported = await export_all(session)

    written: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for rel_path, data in exported.items():
        target = output_dir / rel_path
        if target.exists() and not force and not dry_run:
            skipped.append(str(rel_path))
            continue
        if dry_run:
            written.append(f"[dry-run] {rel_path}")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            written.append(str(rel_path))
        except OSError as exc:
            errors.append(f"{rel_path}: {exc}")

    return {"written": written, "skipped": skipped, "errors": errors}


async def _main(
    output_dir: Path,
    *,
    dry_run: bool,
    force: bool,
    database_url: str,
) -> int:
    engine = create_async_engine(database_url, echo=False)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    async with factory() as session:
        result = await run_export(session, output_dir, dry_run=dry_run, force=force)

    if result["written"]:
        label = "[dry-run]" if dry_run else "Exported"
        for path in result["written"]:
            print(f"{label} {path}")

    if result["skipped"]:
        for path in result["skipped"]:
            print(f"Skipped (already exists, use --force to overwrite): {path}")

    if result["errors"]:
        for msg in result["errors"]:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    total = len(result["written"]) + len(result["skipped"])
    action = "Would export" if dry_run else "Exported"
    print(f"\n{action} {len(result['written'])} file(s), skipped {len(result['skipped'])} (total {total})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export AI Accelerator database config to JSON files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Destination directory (default: {_DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be exported without writing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy async database URL (default: read from DATABASE_URL env var)",
    )
    return parser


if __name__ == "__main__":
    import os

    args = _build_parser().parse_args()
    db_url = args.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "ERROR: No database URL provided. Use --database-url or set DATABASE_URL env var.",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(asyncio.run(_main(args.output_dir, dry_run=args.dry_run, force=args.force, database_url=db_url)))
