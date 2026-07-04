from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.infrastructure.tables.base import Base
from app.infrastructure.tables import fix_table, issue_table  # noqa: F401


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_database() -> None:
    Base.metadata.create_all(bind=engine)
