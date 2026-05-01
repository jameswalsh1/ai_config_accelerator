"""Shared test fixtures.

Redirects every service's DATA_DIR to a per-session copy under
``tests/.test_output/`` so that tests never mutate production config files.

The copy is created once per session and removed when the session ends.
``.test_output/`` is listed in the root ``.gitignore``.
"""

import shutil
from pathlib import Path

import pytest

# Production config data
_PROD_DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs"
# Isolated test copy (written to during tests, cleaned up after)
_TEST_OUTPUT_DIR = Path(__file__).parent / ".test_output"
_TEST_DATA_DIR = _TEST_OUTPUT_DIR / "wizard_configs"

# All modules whose DATA_DIR needs redirecting
_DATA_DIR_MODULES = [
    "app.services.config_persistence",
    "app.services.config_patcher",
    "app.services.config_loader_composable",
    "app.services.audit_log",
    "app.services.version_history",
]


def _import_module(dotted: str):
    """Import a module by its dotted path."""
    import importlib
    return importlib.import_module(dotted)


@pytest.fixture(autouse=True, scope="session")
def _redirect_data_dir():
    """
    Copy production data into .test_output/ and redirect every
    service's DATA_DIR there for the entire test session.

    Cleaned up automatically after all tests finish.
    """
    # Clean slate (ignore errors from concurrent test discovery runs)
    if _TEST_OUTPUT_DIR.exists():
        shutil.rmtree(_TEST_OUTPUT_DIR, ignore_errors=True)

    # Copy production data (ignoring audit.jsonl and history/)
    shutil.copytree(
        _PROD_DATA_DIR,
        _TEST_DATA_DIR,
        ignore=shutil.ignore_patterns("audit.jsonl", "history", "*.backup"),
    )

    # Patch DATA_DIR in every module
    originals: dict[str, Path] = {}
    for dotted in _DATA_DIR_MODULES:
        mod = _import_module(dotted)
        originals[dotted] = getattr(mod, "DATA_DIR")
        setattr(mod, "DATA_DIR", _TEST_DATA_DIR)

    # Also patch derived paths that are computed at import time
    audit_mod = _import_module("app.services.audit_log")
    original_log_path = audit_mod.LOG_PATH
    audit_mod.LOG_PATH = _TEST_DATA_DIR / "audit.jsonl"

    history_mod = _import_module("app.services.version_history")
    original_history_dir = history_mod.HISTORY_DIR
    history_mod.HISTORY_DIR = _TEST_DATA_DIR / "history"

    yield _TEST_DATA_DIR

    # Restore originals
    for dotted, original in originals.items():
        mod = _import_module(dotted)
        setattr(mod, "DATA_DIR", original)
    audit_mod.LOG_PATH = original_log_path
    history_mod.HISTORY_DIR = original_history_dir

    # Remove test output
    if _TEST_OUTPUT_DIR.exists():
        shutil.rmtree(_TEST_OUTPUT_DIR)
