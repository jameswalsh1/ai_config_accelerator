"""Ticket 13 — Pre-cutover backup command.

Creates a timestamped backup directory containing:
- A JSON snapshot of all live database config (via ``export_config_db_to_json``)
- A copy of the existing JSON config files from the data directory
- A ``backup-manifest.json`` with metadata about when/why the backup was taken

Usage
-----
    python -m app.commands.pre_cutover_backup [--backup-dir PATH] [--label LABEL] [--dry-run]

Options
-------
``--backup-dir PATH``
    Root directory for backups.  A timestamped subdirectory is created
    inside it.  Defaults to ``backend/backups/``.
``--label LABEL``
    Optional human-readable label appended to the directory name.
``--dry-run``
    Print what would happen without creating any files.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.commands.export_config_db_to_json import run_export


_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "wizard_configs"
_DEFAULT_BACKUP_ROOT = Path(__file__).resolve().parents[4] / "backups"


async def run_backup(
    session: AsyncSession,
    backup_dir: Path,
    source_data_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Create the backup in ``backup_dir``.

    Returns a manifest dict with the results of both the JSON-file copy and
    the DB export.
    """
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # 1. Copy existing JSON config files
    # -----------------------------------------------------------------------
    json_backup_dir = backup_dir / "json_source"
    json_files_copied: list[str] = []
    if source_data_dir.exists():
        if dry_run:
            for f in source_data_dir.rglob("*.json"):
                json_files_copied.append(str(f.relative_to(source_data_dir)))
        else:
            shutil.copytree(str(source_data_dir), str(json_backup_dir), dirs_exist_ok=True)
            for f in json_backup_dir.rglob("*.json"):
                json_files_copied.append(str(f.relative_to(json_backup_dir)))

    # -----------------------------------------------------------------------
    # 2. Export DB config to JSON
    # -----------------------------------------------------------------------
    db_export_dir = backup_dir / "db_export"
    db_export_result = await run_export(
        session, db_export_dir, dry_run=dry_run, force=True
    )

    # -----------------------------------------------------------------------
    # 3. Write manifest
    # -----------------------------------------------------------------------
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_dir": str(backup_dir),
        "dry_run": dry_run,
        "json_source": {
            "source_dir": str(source_data_dir),
            "files_copied": len(json_files_copied),
        },
        "db_export": {
            "files_written": len(db_export_result["written"]),
            "files_skipped": len(db_export_result["skipped"]),
            "errors": db_export_result["errors"],
        },
    }

    if not dry_run:
        manifest_path = backup_dir / "backup-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return manifest


async def _main(
    backup_root: Path,
    label: str | None,
    *,
    dry_run: bool,
    database_url: str,
) -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dir_name = f"{timestamp}-{label}" if label else timestamp
    backup_dir = backup_root / dir_name

    engine = create_async_engine(database_url, echo=False)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    async with factory() as session:
        manifest = await run_backup(
            session,
            backup_dir,
            _DEFAULT_DATA_DIR,
            dry_run=dry_run,
        )

    if dry_run:
        print("[dry-run] Backup manifest (not written):")
    else:
        print(f"Backup created at: {backup_dir}")
    print(json.dumps(manifest, indent=2))

    if manifest["db_export"]["errors"]:
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a pre-cutover backup of AI Accelerator config."
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=_DEFAULT_BACKUP_ROOT,
        help=f"Root backup directory (default: {_DEFAULT_BACKUP_ROOT})",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label appended to the timestamped directory name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without creating any files",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy async database URL (default: DATABASE_URL env var)",
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
    sys.exit(
        asyncio.run(
            _main(
                args.backup_dir,
                args.label,
                dry_run=args.dry_run,
                database_url=db_url,
            )
        )
    )
