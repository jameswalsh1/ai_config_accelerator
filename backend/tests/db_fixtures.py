"""Database test infrastructure.

Provides fixtures for testing database-backed code.

Current state (Phase 1)
-----------------------
No application tables exist yet.  The fixtures here establish the testing
pattern that later tickets will use when ORM models are introduced.

Strategy
--------
- Unit tests: mock the database session (no live DB required).
- Integration tests: use a real MySQL database identified by the
  ``TEST_DATABASE_URL`` environment variable.

If ``TEST_DATABASE_URL`` is not set, integration tests are skipped
automatically so that the standard ``make test`` run (which does not
require a live MySQL) continues to pass in CI and in local development.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from unittest.mock import AsyncMock, MagicMock

from app.db.base import Base

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


def _requires_live_db() -> pytest.MarkDecorator:
    """Skip marker for tests that need a real MySQL database."""
    return pytest.mark.skipif(
        not _TEST_DATABASE_URL,
        reason=(
            "TEST_DATABASE_URL is not set. "
            "Provide a MySQL connection string to run DB integration tests."
        ),
    )


# ---------------------------------------------------------------------------
# Mock session fixtures (no live DB needed)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a mock ``AsyncSession`` for unit tests.

    Use this when you want to test that service code calls the session
    correctly without needing a live database::

        async def test_my_service(mock_db_session):
            await my_service.do_something(mock_db_session)
            mock_db_session.add.assert_called_once()
    """
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Live DB fixtures (skipped when TEST_DATABASE_URL is not set)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_db_engine():
    """Create a test engine for the session.  Skipped without TEST_DATABASE_URL."""
    if not _TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(_TEST_DATABASE_URL, echo=False)
    yield engine
    # Cleanup is handled by the event loop — engine.dispose() is async
    # and cannot be called from a sync fixture teardown at session scope.
    # The connection pool will be closed when the process exits.


@pytest_asyncio.fixture(scope="session")
async def live_db_schema(live_db_engine: AsyncEngine):
    """Create all tables before tests and drop them afterwards."""
    async with live_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with live_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def live_db_session(
    live_db_engine: AsyncEngine,
    live_db_schema: None,  # ensures schema is created before any session opens
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional ``AsyncSession`` that rolls back after each test.

    Each test runs inside a transaction that is rolled back on completion,
    leaving the database in a clean state for the next test.
    """
    factory = async_sessionmaker(
        bind=live_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()
