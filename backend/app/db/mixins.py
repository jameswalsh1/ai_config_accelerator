"""Reusable audit column mixin for future SQLAlchemy ORM models.

Every application table that needs audit information (created_at, updated_at,
created_by, updated_by) should inherit from ``AuditMixin`` *before* defining
its own columns.

Actor columns use plain ``String`` so they are compatible with the current
header-based auth system (``x-auth-user`` username) and with a future SSO
integration without requiring a schema change.

When auth is disabled, the actor value defaults to ``"system"`` (or
``"anonymous"`` for requests that pass through without an authenticated user).
These values are defined in ``app.services.auth`` and should be used
consistently by all write paths.

Future compatibility
--------------------
When a full user table is introduced (Phase N), ``created_by`` /
``updated_by`` may gain a foreign-key relationship to the user table.
That addition can be made without changing the column types because the
values are already stored as strings (usernames).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditMixin:
    """Mixin that adds standard audit timestamp and actor columns.

    Include this mixin in every application table that requires change
    tracking::

        class MyModel(AuditMixin, Base):
            __tablename__ = "my_table"
            id: Mapped[int] = mapped_column(primary_key=True)
            ...

    Column conventions
    ------------------
    created_at : UTC timestamp set once on insert; never updated.
    updated_at : UTC timestamp updated on every write.
    created_by : String actor identifier (username or "system").
    updated_by : String actor identifier (username or "system").
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
        default="system",
        nullable=False,
    )
    updated_by: Mapped[str] = mapped_column(
        String(255),
        default="system",
        nullable=False,
    )
