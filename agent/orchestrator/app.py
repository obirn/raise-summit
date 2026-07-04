"""Orchestrator FastAPI service — the only interface the coordinator UI uses.

REST + WS (MASTER_PROMPT §3). Mutating endpoints run the (sync) Engine in a
threadpool; the Engine emits ServerEvents which are fanned out to WS clients via
the event loop. The monitoring tick is deterministic time-math and touches no
portal (invariant 2); Computer Use runs only when an alert dispatches it.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..audit.artifacts import ARTIFACTS_DIR

from ..board.board import Board
from ..board.models import AlertKind
from ..computer_use.base import ComputerUse
from ..computer_use.stub import StubComputerUse
from ..monitoring.engine import tick
from ..voice.stub import StubVoice
from . import events as ev
from .engine import Engine
from seed.scenario import DEMO_NOW, seed_board

load_dotenv()

ENV_ID = os.environ.get("ENV_ID", "default")
DB_PATH = os.environ.get("BOARD_DB_PATH", "board.db")
CU_MODE = os.environ.get("CU_MODE", "stub")  # stub (deterministic) | real (Gemini CU)


def _make_cu() -> ComputerUse:
    """Real Gemini Computer Use when CU_MODE=real (needs GEMINI_API_KEY + display);
    otherwise the deterministic offline stub. Falls back to the stub on failure so
    the demo/tests never hard-crash on CU setup."""
    if CU_MODE == "real":
        try:
            from ..computer_use.gemini_cu import RealComputerUse
            return RealComputerUse()
        except Exception:  # noqa: BLE001
            logging.getLogger("orchestrator").exception(
                "CU_MODE=real failed to start; falling back to stub")
    return StubComputerUse()


class ConnectionManager:
    """Fan-out of ServerEvents to connected WS clients, safe to call from the
    threadpool where the sync Engine runs."""

    def __init__(self) -> None:
        self.clients: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def broadcast(self, event: dict) -> None:
        if self.loop is None:
            return
        for q in list(self.clients):
            self.loop.call_soon_threadsafe(q.put_nowait, event)


manager = ConnectionManager()
board = Board.resume(ENV_ID, DB_PATH)
# Seed on first boot (empty env). `make reset` wipes the DB to force a re-seed.
if not board.all():
    seed_board(board, DEMO_NOW)
engine = Engine(board, _make_cu(), StubVoice(), on_event=manager.broadcast)

app = FastAPI(title="Unblock orchestrator")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="artifacts")


@app.on_event("startup")
async def _startup() -> None:
    manager.loop = asyncio.get_running_loop()


# ---- REST ------------------------------------------------------------------
@app.get("/board")
def get_board() -> list[dict]:
    return [c.model_dump(mode="json") for c in board.all()]


class ApproveBody(BaseModel):
    container_id: str
    action_id: str


class DismissBody(BaseModel):
    container_id: str
    alert_id: str


class CallBody(BaseModel):
    demo: bool = True
    container_id: str | None = None


@app.post("/approve", status_code=202)
def approve(body: ApproveBody) -> dict:
    engine.approve(body.container_id, body.action_id)
    return {"accepted": True}


@app.post("/dismiss", status_code=202)
def dismiss(body: DismissBody) -> dict:
    engine.dismiss(body.container_id, body.alert_id)
    return {"accepted": True}


@app.post("/events/call", status_code=202)
def inbound_call(body: CallBody) -> dict:
    engine.on_call(hint=body.container_id)
    return {"accepted": True}


@app.post("/monitor/tick", status_code=202)
def monitor_tick() -> dict:
    """Run the alert engine on held state and dispatch a read for the top
    OVERDUE/STALL alert. DEMO driver for golden-path step 1."""
    alerts = tick(board.all(), DEMO_NOW)
    dispatched = []
    seen: set[str] = set()
    for a in sorted(alerts, key=lambda x: -x.severity):
        if a.kind in (AlertKind.OVERDUE, AlertKind.STALL) and a.container_id not in seen:
            seen.add(a.container_id)
            engine.on_alert(a.container_id, a.responsible_system, a.kind)
            dispatched.append(a.container_id)
    return {"accepted": True, "dispatched": dispatched,
            "alerts": [a.model_dump(mode="json") for a in alerts]}


# ---- WS --------------------------------------------------------------------
@app.websocket("/board/stream")
async def board_stream(ws: WebSocket) -> None:
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    manager.clients.add(q)
    try:
        # send a full snapshot on connect
        for c in board.all():
            await ws.send_json(ev.board_update(c))
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        manager.clients.discard(q)
