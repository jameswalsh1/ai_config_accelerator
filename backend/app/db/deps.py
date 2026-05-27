"""FastAPI dependency for injecting an ``AsyncSession``.

Import and use in route handlers::

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.deps import get_db_session

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db_session)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session as _get_db_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-compatible dependency that yields a managed ``AsyncSession``."""
    async for session in _get_db_session():
        yield session


async def require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for DB-only endpoints.

    This is the canonical dependency used by all DB-only routers.
    Override this in tests via ``app.dependency_overrides`` to supply a
    test SQLite session.
    """
    async for session in _get_db_session():
        yield session
