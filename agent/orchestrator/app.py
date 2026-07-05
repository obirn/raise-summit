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
from ..board.models import AlertKind, FieldTruth
from ..computer_use.base import ComputerUse
from ..computer_use.stub import StubComputerUse
from ..monitoring.engine import tick
from ..voice.stub import StubVoice
from ..solver.manager import AgentManager
from . import events as ev
from .engine import Engine
from seed.scenario import DEMO_NOW, seed_board

load_dotenv()

ENV_ID = os.environ.get("ENV_ID", "default")
DB_PATH = os.environ.get("BOARD_DB_PATH", "board.db")
CU_MODE = os.environ.get("CU_MODE", "stub")  # stub (deterministic) | real (Gemini CU)
# deterministic (hardcoded diagnose) | agentic (LLM solver agents spawn per container)
AGENT_MODE = os.environ.get("AGENT_MODE", "deterministic")
AGENT_BRAIN = os.environ.get("AGENT_BRAIN", "scripted")  # scripted (offline) | gemini
# stub (log only) | bridge (speak the resolution back into the OPEN live call)
VOICE_MODE = os.environ.get("VOICE_MODE", "stub")


def _make_voice() -> "StubVoice":
    """Live speak-back to the driver when VOICE_MODE=bridge (needs `make voice`
    running); otherwise the offline logging stub. Falls back to the stub on any
    import/setup failure so the demo/tests never hard-crash."""
    if VOICE_MODE == "bridge":
        try:
            from ..voice.bridge_client import BridgeVoice
            return BridgeVoice()  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            logging.getLogger("orchestrator").exception(
                "VOICE_MODE=bridge failed to init; falling back to stub")
    return StubVoice()


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
engine = Engine(board, _make_cu(), _make_voice(), on_event=manager.broadcast)
# Agentic layer: the orchestrator spawns one durable solver agent per stuck
# container (only used when AGENT_MODE=agentic).
agents = AgentManager(engine, manager.broadcast, brain_kind=AGENT_BRAIN)

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
    if AGENT_MODE == "agentic":
        # human approves -> the solver agent resumes and executes the fix
        engine.mark_approved(body.container_id, body.action_id)
        agents.resume_after_approve(body.container_id)
    else:
        engine.approve(body.container_id, body.action_id)
    return {"accepted": True}


@app.post("/dismiss", status_code=202)
def dismiss(body: DismissBody) -> dict:
    engine.dismiss(body.container_id, body.alert_id)
    return {"accepted": True}


@app.post("/events/call", status_code=202)
def inbound_call(body: CallBody) -> dict:
    """Pull path — scripted demo. The real telephony bridge uses the push
    endpoints below instead."""
    if AGENT_MODE == "agentic":
        truth = engine.take_call_truth(hint=body.container_id)
        engine.record_voice_truth(truth)
        agents.spawn(truth.container_id, hint_system="terminal")
    else:
        engine.on_call(hint=body.container_id)
    return {"accepted": True}


# ---- push path: the Twilio bridge is the only caller of these ---------------
class FieldTruthBody(BaseModel):
    container_id: str
    reference: str
    blocker_type: str = "unpaid_detention"
    lang: str = "es"
    raw_transcript: str = ""


class CallStartedBody(BaseModel):
    container_id: str | None = None


class TranscriptBody(BaseModel):
    container_id: str | None = None
    speaker: str
    text: str


@app.post("/events/field-truth", status_code=202)
def field_truth(body: FieldTruthBody) -> dict:
    """A real driver call yielded the exact reference. Drives the same flow as
    the scripted demo: targeted terminal read -> surfaced line -> human gate."""
    truth = FieldTruth(
        container_id=body.container_id, blocker_type=body.blocker_type,
        reference=body.reference, lang=body.lang, raw_transcript=body.raw_transcript,
    )
    if AGENT_MODE == "agentic":
        engine.record_voice_truth(truth)
        agents.spawn(truth.container_id, hint_system="terminal")
    else:
        engine.ingest_field_truth(truth)
    return {"accepted": True}


@app.post("/events/call-started", status_code=202)
def call_started(body: CallStartedBody) -> dict:
    manager.broadcast(ev.call_started(body.container_id))
    return {"accepted": True}


@app.post("/events/transcript", status_code=202)
def transcript(body: TranscriptBody) -> dict:
    manager.broadcast(ev.transcript(body.container_id, body.speaker, body.text))
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
            if AGENT_MODE == "agentic":
                # spawn a durable solver agent for this container (parallel portfolio)
                engine.begin_diagnosis(a.container_id, a.responsible_system, a.kind)
                agents.spawn(a.container_id,
                             hint_system=a.responsible_system.value if a.responsible_system else None)
            else:
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
