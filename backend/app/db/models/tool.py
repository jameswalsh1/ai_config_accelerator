"""ORM model for AI tool registry (Ticket 1)."""

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class AITool(AuditMixin, Base):
    """Registry of supported AI tools (claude, copilot, cursor …)."""

    __tablename__ = "ai_tool"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tool_key", name="uq_ai_tool_key"),
        Index("ix_ai_tool_key", "tool_key"),
    )

    def __repr__(self) -> str:
        return f"<AITool id={self.id} tool_key={self.tool_key!r}>"
