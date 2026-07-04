from datetime import date

from sqlalchemy import Date, Enum, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.tables.base import Base
from app.service.models.issue import IssueStatus, IssueType


class IssueTable(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    detection: Mapped[str] = mapped_column(String, nullable=False)
    issue_type: Mapped[IssueType] = mapped_column(
        Enum(IssueType, native_enum=False),
        nullable=False,
    )
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, native_enum=False),
        nullable=False,
        default=IssueStatus.OPEN,
    )
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    updated_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        onupdate=date.today,
    )

    fixes = relationship(
        "FixTable",
        back_populates="issue",
        cascade="all, delete-orphan",
    )
