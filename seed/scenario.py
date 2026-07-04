"""Golden-path seed (MASTER_PROMPT §11). Deterministic: fixed clock in DEMO_MODE.

This seeds the AGENT board (timers + free-time + held state). Portal *truth*
(what Computer Use will read on screen) lives in the frontend portals and is
aligned separately — it is NEVER written here (invariant 1). The primary
container MSKU4471 is stalled by a terminal detention that is invisible on every
monitored portal; only the driver's voice reference DET-4471-B reveals it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.board.board import Board
from agent.board.models import (
    Container,
    ContainerStatus,
    FreeTime,
    LiableParty,
    System,
    Timer,
)

# Fixed demo clock so the golden path runs identically every time.
DEMO_NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)

PRIMARY_CONTAINER_ID = "MSKU4471"
TERMINAL_REFERENCE = "DET-4471-B"      # discoverable only via the driver call
TERMINAL_DETENTION_USD = 340.0


def build_containers(now: datetime = DEMO_NOW, env_id: str = "default") -> list[Container]:
    return [
        # --- the golden path: stalled, cause on no monitored portal ---------
        Container(
            id=PRIMARY_CONTAINER_ID,
            carrier="MAEU",
            port="Valencia",
            status=ContainerStatus.moving,
            env_id=env_id,
            timers=[
                Timer(name="arrival", due_at=now - timedelta(days=1),
                      satisfied=True, satisfied_by="discharged"),
                Timer(name="customs_clearance", due_at=now - timedelta(hours=6),
                      satisfied=True, satisfied_by="customs_released",
                      responsible_system=System.customs),
                Timer(name="gate_out", due_at=now - timedelta(hours=2),
                      satisfied=False, satisfied_by="gated_out",
                      responsible_system=System.terminal, severity_weight=2.0),
                Timer(name="empty_return", due_at=now + timedelta(days=3),
                      satisfied=False, responsible_system=System.carrier),
            ],
            free_time=FreeTime(
                free_days=4,
                free_expires_at=now + timedelta(hours=6),   # within DEMURRAGE_WARN
                days_accrued=0,
                dollars_at_risk=TERMINAL_DETENTION_USD,
                liable_party=LiableParty.importer,
            ),
            last_progress_at=now - timedelta(hours=2),
        ),
        # --- decoy: healthy, no alert ---------------------------------------
        Container(
            id="MSKU5501",
            carrier="MAEU",
            port="Valencia",
            status=ContainerStatus.moving,
            env_id=env_id,
            timers=[
                Timer(name="gate_out", due_at=now + timedelta(days=2),
                      satisfied=False, satisfied_by="gated_out",
                      responsible_system=System.terminal),
            ],
            free_time=FreeTime(free_days=5, free_expires_at=now + timedelta(days=2),
                               dollars_at_risk=0.0, liable_party=LiableParty.importer),
            last_progress_at=now - timedelta(minutes=30),
        ),
        # --- decoy: screen-only customs HS-code hold (no voice needed) -------
        Container(
            id="TCLU3380",
            carrier="MSC",
            port="Valencia",
            status=ContainerStatus.moving,
            env_id=env_id,
            timers=[
                Timer(name="customs_clearance", due_at=now - timedelta(hours=1),
                      satisfied=False, satisfied_by="customs_released",
                      responsible_system=System.customs, severity_weight=1.5),
            ],
            free_time=FreeTime(free_days=3, free_expires_at=now + timedelta(hours=10),
                               dollars_at_risk=180.0, liable_party=LiableParty.importer),
            last_progress_at=now - timedelta(hours=1),
        ),
    ]


def seed_board(board: Board, now: datetime = DEMO_NOW) -> Board:
    """Wipe + re-seed one environment deterministically."""
    board.reset()
    for c in build_containers(now=now, env_id=board.env_id):
        board.upsert(c)
    return board
