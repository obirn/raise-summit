"""The board — durable exception state (invariant 4).

One SQLite file can hold many resumable environments (keyed by env_id). Each
`Container` is stored as one row whose `payload` column is the full serialized
domain object, so `Board.resume(env_id)` re-hydrates losslessly after a crash.

This is the AGENT's own state, deliberately separate from portal state (which
lives only in the browser's localStorage and is reachable solely via Computer
Use). Nothing here ever touches a portal.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .models import AuditEntry, Container

DEFAULT_DB_PATH = os.environ.get("BOARD_DB_PATH", "board.db")


class ContainerRow(SQLModel, table=True):
    """Storage row. `payload` is the source of truth; scalar columns are for
    cheap querying / snapshots only."""

    env_id: str = Field(primary_key=True)
    id: str = Field(primary_key=True)
    status: str = ""
    carrier: str = ""
    port: str = ""
    payload: str = ""  # Container.model_dump_json()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Board:
    """A handle to one resumable environment inside the SQLite file."""

    def __init__(self, env_id: str = "default", db_path: str = DEFAULT_DB_PATH) -> None:
        self.env_id = env_id
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self.engine)

    # ---- reads -------------------------------------------------------------
    def get(self, container_id: str) -> Container | None:
        with Session(self.engine) as s:
            row = s.get(ContainerRow, (self.env_id, container_id))
            return Container.model_validate_json(row.payload) if row else None

    def all(self) -> list[Container]:
        with Session(self.engine) as s:
            rows = s.exec(
                select(ContainerRow).where(ContainerRow.env_id == self.env_id)
            ).all()
        containers = [Container.model_validate_json(r.payload) for r in rows]
        # Deterministic order: highest dollars_at_risk first, then id.
        containers.sort(
            key=lambda c: (
                -(c.free_time.dollars_at_risk if c.free_time else 0.0),
                c.id,
            )
        )
        return containers

    # ---- writes ------------------------------------------------------------
    def upsert(self, container: Container) -> Container:
        """Persist the whole container. Callers write the board BEFORE any side
        effect (invariant 4) so a crash resumes cleanly."""
        container.env_id = self.env_id
        with Session(self.engine) as s:
            row = s.get(ContainerRow, (self.env_id, container.id))
            if row is None:
                row = ContainerRow(env_id=self.env_id, id=container.id)
            row.status = container.status.value
            row.carrier = container.carrier
            row.port = container.port
            row.payload = container.model_dump_json()
            s.add(row)
            s.commit()
        return container

    def log_audit(self, container_id: str, entry: AuditEntry) -> Container:
        """Append an audit entry and persist. Log-then-act (invariant 5)."""
        container = self.get(container_id)
        if container is None:
            raise KeyError(f"unknown container {container_id!r} in env {self.env_id!r}")
        container.action_log.append(entry)
        return self.upsert(container)

    # ---- lifecycle ---------------------------------------------------------
    @classmethod
    def resume(cls, env_id: str = "default", db_path: str = DEFAULT_DB_PATH) -> "Board":
        """Re-hydrate a board from disk. No state lives only in memory."""
        return cls(env_id=env_id, db_path=db_path)

    def reset(self) -> None:
        """Wipe this environment's containers (deterministic re-seed)."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(ContainerRow).where(ContainerRow.env_id == self.env_id)
            ).all()
            for r in rows:
                s.delete(r)
            s.commit()
