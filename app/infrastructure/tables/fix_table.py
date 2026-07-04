from datetime import date

from typing import Any

from sqlalchemy import Date, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.tables.base import Base
from app.service.models.fix import FixResult


class FixTable(Base):
    __tablename__ = "fixes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), nullable=False, index=True)
    action_details: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[FixResult | None] = mapped_column(
        Enum(FixResult, native_enum=False),
        nullable=True,
    )
    execution_log: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    human_input: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    updated_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        onupdate=date.today,
    )

    issue = relationship("IssueTable", back_populates="fixes")
