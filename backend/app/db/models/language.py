"""ORM model for programming language registry (Ticket 1)."""

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Language(AuditMixin, Base):
    """Registry of supported programming languages (python, java, typescript …)."""

    __tablename__ = "language"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    language_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("language_key", name="uq_language_key"),
        Index("ix_language_key", "language_key"),
    )

    def __repr__(self) -> str:
        return f"<Language id={self.id} language_key={self.language_key!r}>"
