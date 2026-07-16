"""Async SQLAlchemy engine and session factory.

The engine is created lazily on first use so that tests can patch
``DatabaseSettings`` before the module is exercised.

Usage
-----
Prefer injecting ``AsyncSession`` via ``app.db.deps.get_db_session`` in
FastAPI route handlers rather than accessing ``AsyncSessionLocal`` directly.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings import get_database_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Return the singleton async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_database_settings()
        _engine = create_async_engine(
            settings.get_url(),
            echo=False,
            pool_pre_ping=True,  # verifies connections before use
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_pool_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            connect_args=settings.get_connect_args(),
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton async session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator that yields an ``AsyncSession`` and closes it on exit.

    Intended for use as a FastAPI dependency (``Depends(get_db_session)``).
    The caller is responsible for committing or rolling back the transaction.

    Example::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(MyModel))
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
