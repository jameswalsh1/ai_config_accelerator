"""
Version History Service

Stores immutable, sequentially-numbered copies of configuration files
so that every saved version can be retrieved and compared later.

Layout on disk::

    data/wizard_configs/history/{scope}/{target}/
        v001.json
        v002.json
        ...

Each version file is a thin wrapper::

    {
        "version": 3,
        "timestamp": "2026-04-30T14:00:00+00:00",
        "actor": "system",
        "summary": "step 'claude_md': 1 field(s) modified",
        "data": { ... full config content ... }
    }

The service is intentionally simple — no locking beyond what the
filesystem provides.  Version numbers are derived from filenames so
no manifest file is needed.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"
HISTORY_DIR = DATA_DIR / "history"


def _history_dir(scope: str, target: str) -> Path:
    return HISTORY_DIR / scope / target


def _version_path(scope: str, target: str, version: int) -> Path:
    return _history_dir(scope, target) / f"v{version:03d}.json"


def _next_version(scope: str, target: str) -> int:
    """Return the next version number (1-based)."""
    d = _history_dir(scope, target)
    if not d.exists():
        return 1
    existing = sorted(d.glob("v[0-9][0-9][0-9].json"))
    if not existing:
        return 1
    # Parse highest version number
    last = existing[-1].stem  # e.g. "v003"
    return int(last[1:]) + 1


def save_version(
    scope: str,
    target: str,
    data: dict[str, Any],
    actor: str = "system",
    summary: str = "",
) -> dict[str, Any]:
    """
    Save a new version of the config to the history directory.

    Args:
        scope:   "tool", "language", or "override"
        target:  e.g. "python", "claude"
        data:    Full config dict to archive
        actor:   Identity of the author
        summary: Human-readable change summary

    Returns:
        Version metadata dict (without the ``data`` payload).
    """
    version = _next_version(scope, target)
    timestamp = datetime.now(timezone.utc).isoformat()

    envelope: dict[str, Any] = {
        "version": version,
        "timestamp": timestamp,
        "actor": actor,
        "summary": summary,
        "data": data,
    }

    d = _history_dir(scope, target)
    d.mkdir(parents=True, exist_ok=True)
    dest = _version_path(scope, target, version)

    # Atomic write
    temp_fd, temp_path_str = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    temp_path = Path(temp_path_str)
    os.close(temp_fd)
    try:
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        temp_path.replace(dest)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise

    return {
        "version": version,
        "timestamp": timestamp,
        "actor": actor,
        "summary": summary,
        "scope": scope,
        "target": target,
    }


def list_versions(scope: str, target: str) -> list[dict[str, Any]]:
    """
    List all versions for a scope+target, newest first.

    Returns a list of metadata dicts (no ``data`` payload).
    """
    d = _history_dir(scope, target)
    if not d.exists():
        return []

    versions: list[dict[str, Any]] = []
    for path in sorted(d.glob("v[0-9][0-9][0-9].json"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                envelope = json.load(f)
            versions.append({
                "version": envelope["version"],
                "timestamp": envelope.get("timestamp", ""),
                "actor": envelope.get("actor", "system"),
                "summary": envelope.get("summary", ""),
                "scope": scope,
                "target": target,
            })
        except Exception:
            continue  # skip corrupt files

    return versions


def get_version(scope: str, target: str, version: int) -> dict[str, Any]:
    """
    Return the full envelope (metadata + data) for a specific version.

    Raises:
        FileNotFoundError: If the version does not exist.
    """
    path = _version_path(scope, target, version)
    if not path.exists():
        raise FileNotFoundError(
            f"Version {version} not found for {scope}/{target}"
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_version_data(scope: str, target: str, version: int) -> dict[str, Any]:
    """
    Return just the config data for a specific version.

    Raises:
        FileNotFoundError: If the version does not exist.
    """
    envelope = get_version(scope, target, version)
    return envelope["data"]


def get_latest_version_number(scope: str, target: str) -> int | None:
    """Return the latest version number, or None if no history exists."""
    n = _next_version(scope, target)
    return n - 1 if n > 1 else None
