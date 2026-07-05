"""The alert engine — detection is time math on held state, never perception.

`tick(containers, now)` is a pure function of the board snapshot and the clock.
It touches NO portal (invariant 2): Computer Use is dispatched later, only when
an alert decides a read is worth its cost. Kept pure so it is unit-testable
without the network.
"""

from __future__ import annotations

from datetime import datetime

from ..board.models import Alert, AlertKind, Container, Timer
from .config import DEMURRAGE_WARN, DWELL_MAX


def urgency(now: datetime, expires: datetime) -> float:
    """Rises as free time runs out. Deterministic, banded for demo clarity."""
    hours_left = (expires - now).total_seconds() / 3600.0
    if hours_left > 48:
        return 1.0
    if hours_left > 12:
        return 2.0
    if hours_left > 0:
        return 4.0
    return 8.0  # already accruing demurrage


def severity(c: Container, t: Timer | None, now: datetime) -> float:
    dollars = c.free_time.dollars_at_risk if c.free_time else 0.0
    u = urgency(now, c.free_time.free_expires_at) if c.free_time else 1.0
    weight = t.severity_weight if t else 1.0
    return dollars * u * weight


def observed(c: Container, satisfied_by: str) -> bool:
    """True if the board already holds the observation that clears a timer."""
    return any(t.satisfied and t.satisfied_by == satisfied_by for t in c.timers)


def _alert_id(kind: AlertKind, container_id: str, timer_name: str | None) -> str:
    return f"{kind.value}:{container_id}:{timer_name or '-'}"


def tick(containers: list[Container], now: datetime) -> list[Alert]:
    """Evaluate timers + free-time clock. Returns alerts; reads no portal."""
    alerts: list[Alert] = []
    for c in containers:
        for t in c.timers:
            if not t.satisfied and now > t.due_at:
                alerts.append(
                    Alert(
                        id=_alert_id(AlertKind.OVERDUE, c.id, t.name),
                        container_id=c.id,
                        kind=AlertKind.OVERDUE,
                        timer_name=t.name,
                        responsible_system=t.responsible_system,
                        severity=severity(c, t, now),
                        ts=now,
                    )
                )

        if (
            c.free_time
            and (c.free_time.free_expires_at - now) < DEMURRAGE_WARN
            and not observed(c, "gated_out")
        ):
            alerts.append(
                Alert(
                    id=_alert_id(AlertKind.DEMURRAGE_RISK, c.id, None),
                    container_id=c.id,
                    kind=AlertKind.DEMURRAGE_RISK,
                    severity=severity(c, None, now),
                    ts=now,
                )
            )

        if c.last_progress_at and (now - c.last_progress_at) > DWELL_MAX:
            alerts.append(
                Alert(
                    id=_alert_id(AlertKind.STALL, c.id, None),
                    container_id=c.id,
                    kind=AlertKind.STALL,
                    severity=severity(c, None, now),
                    ts=now,
                )
            )
    return alerts
