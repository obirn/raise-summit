"""Domain models for Unblock — the data shapes from MASTER_PROMPT §4.

These are the in-memory (Pydantic) representation. The board persists a
`Container` as one JSON payload per row (see board.py) so `resume(env_id)`
re-hydrates losslessly (invariant 4). Enums serialize as their string values.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---- enums -----------------------------------------------------------------
class System(str, Enum):
    tms = "tms"
    carrier = "carrier"
    customs = "customs"
    terminal = "terminal"


class ContainerStatus(str, Enum):
    moving = "moving"
    stalled = "stalled"
    stalled_unlocatable = "stalled_unlocatable"
    diagnosing = "diagnosing"
    awaiting_action = "awaiting_action"
    executing = "executing"
    verifying = "verifying"
    resolving = "resolving"
    released = "released"
    escalated = "escalated"


class AlertKind(str, Enum):
    OVERDUE = "OVERDUE"
    DEMURRAGE_RISK = "DEMURRAGE_RISK"
    STALL = "STALL"
    EVENT = "EVENT"


class CostClass(str, Enum):
    read = "read"
    low = "low"
    high = "high"


class TaskKind(str, Enum):
    read = "read"
    act = "act"


class LiableParty(str, Enum):
    importer = "importer"
    forwarder = "forwarder"


class DiscoveredVia(str, Enum):
    screen = "screen"
    voice = "voice"
    feed = "feed"


class Actor(str, Enum):
    monitor = "monitor"
    cu = "cu"
    voice = "voice"
    human = "human"
    agent = "agent"     # the LLM solver agent (planning decisions)


# ---- container-held state --------------------------------------------------
class Timer(BaseModel):
    name: str                       # arrival | customs_clearance | gate_out | empty_return
    due_at: datetime
    satisfied: bool = False
    satisfied_by: str = ""          # observation that clears it, e.g. "gated_out"
    responsible_system: System | None = None
    severity_weight: float = 1.0


class FreeTime(BaseModel):
    free_days: int                  # DEMO-ONLY: hardcoded per carrier/port
    free_expires_at: datetime
    days_accrued: int = 0
    dollars_at_risk: float = 0.0
    liable_party: LiableParty = LiableParty.importer


class Blocker(BaseModel):
    source_system: System
    type: str                       # "unpaid_detention" | "customs_hold" | ...
    evidence: str                   # human-readable, from CU read or the call
    is_binding: bool = True         # on the critical path?
    discovered_via: DiscoveredVia = DiscoveredVia.screen
    reference: str | None = None    # e.g. "DET-4471-B" (voice-provided)


class AuditEntry(BaseModel):
    ts: datetime
    actor: Actor
    action: str
    target_system: System | None = None
    artifact_path: str | None = None   # screenshot
    result: str = ""


class Alert(BaseModel):
    id: str
    container_id: str
    kind: AlertKind
    timer_name: str | None = None
    responsible_system: System | None = None
    severity: float = 0.0
    ts: datetime


class PendingAction(BaseModel):
    """A gated (cost_class=high) action awaiting a human /approve."""
    action_id: str
    container_id: str
    target_system: System
    goal: str
    params: dict = Field(default_factory=dict)
    cost_class: CostClass = CostClass.high
    line: str = ""                  # the single surfaced plain-language line
    approved: bool = False


class AgentStatus(str, Enum):
    planning = "planning"            # reasoning + reading portals
    awaiting_human = "awaiting_human"  # paused at the human gate (surfaced)
    executing = "executing"          # approved -> CU acting
    done = "done"                    # resolved
    failed = "failed"                # gave up / escalated


class AgentStep(BaseModel):
    ts: datetime
    tool: str                        # read_portal | surface_blocker | ... | done
    args: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    summary: str = ""                # short human line for the UI


class AgentState(BaseModel):
    """A durable, resumable solver agent bound to one container (the 'Antigravity'
    capability). Persisted on the board; killing the process mid-run and resuming
    re-hydrates the agent's plan and step log."""
    agent_id: str
    container_id: str
    status: AgentStatus = AgentStatus.planning
    goal: str = ""
    steps: list[AgentStep] = Field(default_factory=list)
    brain: str = "scripted"          # scripted | gemini | antigravity
    # Antigravity / Interactions API durable-reasoning handles (M6): the agent's
    # reasoning lives server-side; the board keeps only these handles, so a
    # resumed process continues the SAME interaction by id (load-bearing).
    previous_interaction_id: str | None = None
    environment_id: str | None = None      # reused remote sandbox handle
    pending_call_id: str | None = None      # FunctionCallStep.id awaiting its result


class Container(BaseModel):
    id: str
    carrier: str
    port: str
    status: ContainerStatus = ContainerStatus.moving
    timers: list[Timer] = Field(default_factory=list)
    free_time: FreeTime | None = None
    blockers: list[Blocker] = Field(default_factory=list)
    action_log: list[AuditEntry] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    agent: AgentState | None = None            # the solver agent working this container
    env_id: str = "default"
    last_progress_at: datetime | None = None   # for DWELL/STALL math


# ---- transient module contracts (§3 / §4) ----------------------------------
class Task(BaseModel):
    kind: TaskKind
    target_system: System
    goal: str
    params: dict = Field(default_factory=dict)
    cost_class: CostClass = CostClass.read


class Observation(BaseModel):
    container_id: str
    source_system: System
    fields: dict = Field(default_factory=dict)
    screenshot_path: str | None = None
    confidence: float = 1.0
    ts: datetime


class ActionResult(BaseModel):
    ok: bool
    target_system: System
    before_shot: str | None = None
    after_shot: str | None = None
    verified: bool = False
    ts: datetime


class FieldTruth(BaseModel):
    container_id: str
    blocker_type: str
    reference: str
    raw_transcript: str = ""
    lang: str = "es"
