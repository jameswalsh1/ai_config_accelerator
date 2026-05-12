"""Shared test fixtures.

Redirects every service's DATA_DIR to a per-session isolated copy so that
tests never mutate production config files.

A unique temporary directory is created by pytest for each test session via
``tmp_path_factory``.  pytest handles cleanup automatically, which prevents
stale directories from interfering with subsequent runs (e.g. when VS Code
terminates a session before teardown completes).

By default all tests run with CONFIG_SOURCE=json so that non-DB tests are
unaffected by the production default of CONFIG_SOURCE=database.  Tests that
specifically exercise database mode set CONFIG_SOURCE=database themselves.
"""

import importlib
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

# JSON fixture data (used by JSON-mode tests only)
_PROD_DATA_DIR = Path(__file__).parent / "wizard_configs"

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


@pytest.fixture(autouse=True)
def _default_config_source_json():
    """Set CONFIG_SOURCE=json for every test unless it overrides the env var.

    The production default is now ``database``, but most existing tests test
    JSON-mode behaviour and do not provision a test database.  This fixture
    ensures tests that don't explicitly set CONFIG_SOURCE still work.

    Tests that need ``CONFIG_SOURCE=database`` set it themselves and reset
    ``app.settings._config_source_settings = None`` after the test.
    """
    import app.settings as settings_mod

    prev = os.environ.get("CONFIG_SOURCE")
    os.environ["CONFIG_SOURCE"] = "json"
    settings_mod._config_source_settings = None

    yield

    if prev is None:
        os.environ.pop("CONFIG_SOURCE", None)
    else:
        os.environ["CONFIG_SOURCE"] = prev
    settings_mod._config_source_settings = None
