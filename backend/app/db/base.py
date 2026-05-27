"""SQLAlchemy declarative base and shared metadata.

All application ORM models should inherit from ``Base``.  This module is
imported by Alembic's ``env.py`` so that ``alembic revision --autogenerate``
can discover every mapped table automatically.

No application tables are defined here yet — this is the Phase 1 baseline.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass
