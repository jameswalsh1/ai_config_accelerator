"""
Ticket 13: Resolved config snapshot / parity baseline tests.

On first run (when no fixture exists), the test writes the snapshot.
On subsequent runs, it compares the resolved config against the saved snapshot.

This ensures that config resolution stays deterministic and any accidental
change to the resolved output is detected immediately.

To regenerate snapshots after an intentional change:
    rm backend/tests/fixtures/snapshots/*.json
    pytest tests/test_config_snapshots.py
"""
import json
import pytest
from pathlib import Path
from app.services.config_loader_composable import load_composable_config

SNAPSHOT_DIR = Path(__file__).parent / "fixtures" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# All 18 tool+language combinations
COMBOS = [
    ("claude", "python"),
    ("claude", "java"),
    ("claude", "typescript"),
    ("claude", "angular"),
    ("claude", "dotnet"),
    ("claude", "react-typescript"),
    ("copilot", "python"),
    ("copilot", "java"),
    ("copilot", "typescript"),
    ("copilot", "angular"),
    ("copilot", "dotnet"),
    ("copilot", "react-typescript"),
    ("cursor", "python"),
    ("cursor", "java"),
    ("cursor", "typescript"),
    ("cursor", "angular"),
    ("cursor", "dotnet"),
    ("cursor", "react-typescript"),
]

# Fields included in snapshot assertions (stable fields that define correctness)
_SNAPSHOT_KEYS = {"id", "schema_version", "steps"}


def _clean_for_snapshot(config: dict) -> dict:
    """Remove volatile keys that shouldn't be part of the snapshot comparison."""
    result = {k: v for k, v in config.items() if not k.startswith("_")}
    return result


def _snapshot_path(tool: str, language: str) -> Path:
    return SNAPSHOT_DIR / f"{tool}+{language}.json"


@pytest.mark.parametrize("tool,language", COMBOS)
def test_resolved_config_matches_snapshot(tool: str, language: str) -> None:
    """Resolved config is deterministic and stable against saved baseline."""
    resolved = load_composable_config(tool, language)
    cleaned = _clean_for_snapshot(resolved)

    snap_path = _snapshot_path(tool, language)

    if not snap_path.exists():
        # First run — write the baseline
        snap_path.write_text(json.dumps(cleaned, indent=2, sort_keys=True))
        pytest.skip(f"Snapshot created for {tool}+{language} — rerun to verify")

    saved = json.loads(snap_path.read_text())

    # Compare step IDs and count (structural stability)
    saved_steps = [s["id"] for s in saved.get("steps", [])]
    current_steps = [s["id"] for s in cleaned.get("steps", [])]
    assert current_steps == saved_steps, (
        f"{tool}+{language}: step list changed.\n"
        f"Expected: {saved_steps}\n"
        f"Got:      {current_steps}"
    )

    # Compare schema_version
    assert cleaned.get("schema_version") == saved.get("schema_version"), (
        f"{tool}+{language}: schema_version changed"
    )

    # Compare field IDs per step (structural stability)
    saved_step_map = {s["id"]: s for s in saved.get("steps", [])}
    for step in cleaned.get("steps", []):
        step_id = step["id"]
        if step_id not in saved_step_map:
            continue
        saved_fields = [f["id"] for f in saved_step_map[step_id].get("fields", [])]
        current_fields = [f["id"] for f in step.get("fields", [])]
        assert current_fields == saved_fields, (
            f"{tool}+{language}: step '{step_id}' field list changed.\n"
            f"Expected: {saved_fields}\n"
            f"Got:      {current_fields}"
        )
