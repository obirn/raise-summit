"""ServerEvent constructors (MASTER_PROMPT §3, WS /board/stream)."""

from __future__ import annotations

from ..board.models import Container


def board_update(container: Container) -> dict:
    return {"type": "board_update", "container": container.model_dump(mode="json")}


def surfaced_line(container_id: str, action_id: str, line: str, cost_class: str) -> dict:
    return {
        "type": "surfaced_line",
        "container_id": container_id,
        "action_id": action_id,
        "line": line,
        "cost_class": cost_class,
    }


def call_started(container_id: str | None = None) -> dict:
    return {"type": "call_started", "container_id": container_id}


def transcript(container_id: str | None, speaker: str, text: str) -> dict:
    return {"type": "transcript", "container_id": container_id,
            "speaker": speaker, "text": text}


def resolved(container_id: str) -> dict:
    return {"type": "resolved", "container_id": container_id}
