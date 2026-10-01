from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Open', 'In progress', 'Resolved')",
            name="ck_tickets_status",
        ),
        CheckConstraint(
            "priority IN ('Low', 'Normal', 'High')",
            name="ck_tickets_priority",
        ),
        CheckConstraint(
            "category IN ('Account access', 'Hardware', 'Software', 'Network', 'Other')",
            name="ck_tickets_category",
        ),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_assignee", "assignee"),
        Index("ix_tickets_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="Normal")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Open")
    assignee: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def ticket_key(self) -> str:
        return f"TK-{self.id + 1000:04d}"