"""Shared test fixtures.

Redirects every service's DATA_DIR to a per-session isolated copy so that
tests never mutate production config files.

A unique temporary directory is created by pytest for each test session via
``tmp_path_factory``.  pytest handles cleanup automatically, which prevents
stale directories from interfering with subsequent runs (e.g. when VS Code
terminates a session before teardown completes).
"""

import importlib
import shutil
from pathlib import Path
from typing import Any

import pytest

# Production config data
_PROD_DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs"

# All modules whose DATA_DIR needs redirecting
_DATA_DIR_MODULES = [
    "app.services.config_persistence",
    "app.services.config_patcher",
    "app.services.config_loader_composable",
    "app.services.audit_log",
    "app.services.version_history",
]


def _import_module(dotted: str) -> Any:
    """Import a module by its dotted path."""
    return importlib.import_module(dotted)


@pytest.fixture(autouse=True, scope="session")
def _redirect_data_dir(tmp_path_factory):
    """
    Copy production data into a fresh temporary directory and redirect every
    service's DATA_DIR there for the entire test session.

    Uses pytest's tmp_path_factory so each session gets a unique directory.
    pytest handles cleanup, preventing stale directories across runs.
    """
    # Create a unique per-session temp directory and populate it with a copy
    # of the production data (excluding runtime-generated files).
    session_tmp = tmp_path_factory.mktemp("wizard_configs")
    shutil.copytree(
        _PROD_DATA_DIR,
        session_tmp,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("audit.jsonl", "history", "*.backup"),
    )

    # Patch DATA_DIR in every module
    originals: dict[str, Path] = {}
    for dotted in _DATA_DIR_MODULES:
        mod = _import_module(dotted)
        originals[dotted] = getattr(mod, "DATA_DIR")
        setattr(mod, "DATA_DIR", session_tmp)

    # Also patch derived paths that are computed at import time
    audit_mod = _import_module("app.services.audit_log")
    original_log_path = audit_mod.LOG_PATH
    audit_mod.LOG_PATH = session_tmp / "audit.jsonl"

    history_mod = _import_module("app.services.version_history")
    original_history_dir = history_mod.HISTORY_DIR
    history_mod.HISTORY_DIR = session_tmp / "history"

    yield session_tmp

    # Restore originals so subsequent in-process sessions (e.g. VS Code test
    # re-runs) start from the correct production path.
    for dotted, original in originals.items():
        mod = _import_module(dotted)
        setattr(mod, "DATA_DIR", original)
    audit_mod.LOG_PATH = original_log_path
    history_mod.HISTORY_DIR = original_history_dir
