"""Shared test fixtures.

Redirects every service's DATA_DIR to a per-session isolated copy so that
tests never mutate production config files.

A unique temporary directory is created by pytest for each test session via
``tmp_path_factory``.  pytest handles cleanup automatically, which prevents
stale directories from interfering with subsequent runs (e.g. when VS Code
terminates a session before teardown completes).

All tests run with CONFIG_SOURCE=database.  The shared test DB is seeded
once per session from the JSON wizard config fixtures.
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
    "app.services.config_patcher",
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


# ---------------------------------------------------------------------------
# Shared file-based SQLite DB — seeded once per session for all route tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _seed_shared_test_db(tmp_path_factory: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """Create and seed a file-based SQLite DB once per test session.

    A fresh engine is created per-request inside the dependency override so
    that each anyio event loop (used by TestClient) gets its own connection,
    avoiding the 'Future attached to a different loop' error.
    """
    import asyncio
    from pathlib import Path as _Path
    from sqlalchemy.ext.asyncio import (
        AsyncSession as _AsyncSession,
        async_sessionmaker as _asm,
        create_async_engine as _cae,
    )
    from app.db.base import Base as _Base
    from app.commands.import_json_to_db import run_import as _run_import
    from app.db.deps import require_db_session as _rdb
    from app.main import app as _app

    data_dir = _Path(__file__).parent / "wizard_configs"
    db_file = tmp_path_factory.mktemp("route_test_db") / "test.db"
    sqlite_url = f"sqlite+aiosqlite:///{db_file}"

    async def _setup() -> None:
        engine = _cae(sqlite_url, echo=False)
        factory = _asm(engine, expire_on_commit=False, class_=_AsyncSession)
        async with engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        async with factory() as session:
            await _run_import(session, data_dir)
            await session.commit()
        await engine.dispose()

    asyncio.run(_setup())

    async def _db_override():  # type: ignore[return]
        # Create a fresh engine per-request so anyio's event loop owns the connection.
        engine = _cae(sqlite_url, echo=False)
        factory = _asm(engine, expire_on_commit=False, class_=_AsyncSession)
        async with factory() as session:
            yield session
        await engine.dispose()

    _app.dependency_overrides[_rdb] = _db_override

    yield

    _app.dependency_overrides.pop(_rdb, None)


@pytest.fixture(autouse=True)
def _default_config_source_database():
    """Set CONFIG_SOURCE=database for every test.

    The only supported config source is ``database``.  This fixture ensures
    the environment variable is set consistently for all tests.
    """
    import app.settings as settings_mod

    prev = os.environ.get("CONFIG_SOURCE")
    os.environ["CONFIG_SOURCE"] = "database"
    settings_mod._config_source_settings = None

    yield

    if prev is None:
        os.environ.pop("CONFIG_SOURCE", None)
    else:
        os.environ["CONFIG_SOURCE"] = prev
    settings_mod._config_source_settings = None
