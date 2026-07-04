from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.tables.base import Base


class ContainerTable(Base):
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
