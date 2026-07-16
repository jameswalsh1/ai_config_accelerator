"""Standard async transaction helper for database writes.

All database write operations should use ``db_transaction`` (or the
``atomic`` context manager) to ensure that commits and rollbacks happen
consistently across the codebase.

Usage
-----
Option 1 — async context manager::

    async with atomic(session):
        session.add(my_object)
        # commit happens automatically on exit
        # rollback happens automatically on exception

Option 2 — explicit helper for a single callable::

    async def _do_work(session: AsyncSession) -> None:
        session.add(my_object)

    await db_transaction(session, _do_work)

Why this pattern
----------------
Wrapping the config write, audit-log append, and version-history save
in a single transaction ensures that either all three succeed or none
do — eliminating partial-failure modes.
"""

from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that commits on success and rolls back on error.

    The session is yielded so callers can add / update / delete models
    inside the ``async with`` block.

    Example::

        async with atomic(session) as s:
            s.add(MyModel(name="example"))
    """
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def db_transaction(
    session: AsyncSession,
    work: Callable[[AsyncSession], Coroutine[Any, Any, None]],
) -> None:
    """Execute ``work`` inside an atomic transaction.

    Commits if ``work`` completes without raising; rolls back otherwise.

    Args:
        session: An ``AsyncSession`` obtained from ``get_db_session``.
        work:    An async callable that accepts the session and performs
                 all required database operations.

    Raises:
        Any exception raised by ``work`` — after rolling back the session.
    """
    async with atomic(session):
        await work(session)
