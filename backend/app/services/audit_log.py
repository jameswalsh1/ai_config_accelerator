"""
Audit Log Service

Provides an append-only JSONL audit trail of every configuration change.

Each entry records:
- timestamp     ISO-8601 UTC
- action        "create" | "update" | "delete"
- scope         "language" | "tool" | "override" | "unknown"
- target        e.g. "python", "claude"
- file          workspace-relative file path
- actor         identity of the author ("system" until auth is wired in)
- diff_summary  human-readable summary string from config_diff
- diff          full structured diff dict from config_diff

The log lives at DATA_DIR/audit.jsonl alongside the config files.
Audit failures are non-fatal — a failed write never blocks a config save.
"""

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "tests" / "wizard_configs"
LOG_PATH = DATA_DIR / "audit.jsonl"

# Module-level lock so concurrent requests don't interleave JSONL lines
_lock = threading.Lock()


def append_audit_entry(entry: dict[str, Any]) -> None:
    """
    Append a single audit entry to the JSONL log.

    Thread-safe. Raises OSError on file-system failure (caller should
    catch and treat as non-fatal).

    Args:
        entry: Audit record dict. Must be JSON-serialisable.
    """
    line = json.dumps(entry, ensure_ascii=False, default=str)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_audit_log(
    limit: int = 100,
    offset: int = 0,
    scope: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """
    Read entries from the audit log, newest-first.

    Args:
        limit:  Maximum number of entries to return (max 500).
        offset: Number of entries to skip after filtering (for pagination).
        scope:  Optional filter — only return entries matching this scope.
        target: Optional filter — only return entries matching this target.

    Returns:
        {
            "entries": [...],   # list of audit entry dicts
            "total": int,       # total matching entries (before pagination)
        }
    """
    limit = min(limit, 500)

    if not LOG_PATH.exists():
        return {"entries": [], "total": 0}

    with _lock:
        raw_lines = LOG_PATH.read_text(encoding="utf-8").splitlines()

    entries: list[dict[str, Any]] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue  # Skip malformed lines — never crash on a corrupt log

        if scope and entry.get("scope") != scope:
            continue
        if target and entry.get("target") != target:
            continue

        entries.append(entry)

    # Newest first
    entries.reverse()
    total = len(entries)
    return {
        "entries": entries[offset: offset + limit],
        "total": total,
    }


def build_audit_entry(
    file_path: Path,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any],
    context: dict[str, Any] | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    """
    Build a single audit entry dict from before/after config dicts.

    Computes a structured diff using config_diff. Imported lazily to
    avoid circular imports at module load time.

    Args:
        file_path:   Absolute path to the config file that was written.
        before_data: Previous file content, or None for newly created files.
        after_data:  New file content.
        context:     Optional extra metadata (e.g. {"scope": "language", "target": "python"}).
        actor:       Identity of the author.

    Returns:
        Audit entry dict ready for append_audit_entry().
    """
    from app.services.config_diff import compare_configs, diff_to_dict  # lazy import

    context = context or {}

    # Derive action
    action = "create" if before_data is None else "update"

    # Derive scope / target from context, then fall back to path heuristics
    scope = context.get("scope") or _infer_scope(file_path)
    target = context.get("target") or _infer_target(file_path)

    # Actor: context wins over the explicit param (allows caller override)
    resolved_actor = context.get("actor") or actor

    # Compute diff (use an empty dict as "before" for new files)
    before = before_data or {}
    diff_obj = compare_configs(before, after_data)
    diff_dict = diff_to_dict(diff_obj)
    diff_summary = _summarise_diff(diff_obj)

    # Workspace-relative file path for readability
    try:
        relative_file = str(file_path.relative_to(DATA_DIR.parent.parent.parent))
    except ValueError:
        relative_file = str(file_path)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "scope": scope,
        "target": target,
        "file": relative_file,
        "actor": resolved_actor,
        "diff_summary": diff_summary,
        "diff": diff_dict,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _infer_scope(file_path: Path) -> str:
    """Guess scope from file path when not provided in context."""
    parts = file_path.parts
    if "languages" in parts:
        return "language"
    if "tools" in parts:
        return "tool"
    if "overrides" in parts:
        return "override"
    return "unknown"


def _infer_target(file_path: Path) -> str:
    """Guess target (config id) from file stem when not provided in context."""
    return file_path.stem


def _summarise_diff(diff_obj: Any) -> str:
    """
    Produce a short human-readable summary from a ConfigDiff object.

    Falls back gracefully if config_diff internals change.
    """
    try:
        total = diff_obj.get_total_changes() if hasattr(diff_obj, "get_total_changes") else 0
        if total == 0:
            return "no changes"

        parts: list[str] = []
        if getattr(diff_obj, "title_changed", False):
            parts.append("title")
        if getattr(diff_obj, "description_changed", False):
            parts.append("description")

        for step_diff in getattr(diff_obj, "step_diffs", []):
            if not hasattr(step_diff, "has_changes") or not step_diff.has_changes():
                continue
            summary = step_diff.get_change_summary() if hasattr(step_diff, "get_change_summary") else ""
            parts.append(f"step '{step_diff.step_id}': {summary}")

        added = getattr(diff_obj, "steps_added", [])
        removed = getattr(diff_obj, "steps_removed", [])
        if added:
            parts.append(f"added steps: {', '.join(added)}")
        if removed:
            parts.append(f"removed steps: {', '.join(removed)}")

        return "; ".join(parts) if parts else f"{total} change(s)"
    except Exception:
        return "diff unavailable"
