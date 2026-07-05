"""The orchestrator state machine (MASTER_PROMPT §6/§7).

Every transition writes the board BEFORE side effects (invariant 4), so a crash
resumes cleanly. Reads are auto; any high-cost act requires a prior /approve
(invariant 3). The engine talks to portals ONLY through the Computer Use
contract — never a portal backend (invariant 1).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from ..board.board import Board
from ..board.models import (
    ActionResult,
    Actor,
    AlertKind,
    AuditEntry,
    Blocker,
    Container,
    ContainerStatus,
    CostClass,
    DiscoveredVia,
    FieldTruth,
    Observation,
    PendingAction,
    System,
    Task,
    TaskKind,
)
from ..computer_use.base import ComputerUse
from ..voice.base import Voice
from . import events

logger = logging.getLogger("orchestrator")

EventSink = Callable[[dict], None]

# Which systems to read to rule out a cause, and in what order.
_UPSTREAM = [System.tms, System.carrier, System.customs]

# Surfaced-line + one-tap copy per blocker type (§7).
_ACTION_COPY = {
    "unpaid_detention": ("Pay & release", CostClass.high),
    "customs_hold": ("Refile HS code", CostClass.high),
    "carrier_hold": ("Clear carrier hold", CostClass.high),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Engine:
    def __init__(self, board: Board, cu: ComputerUse, voice: Voice,
                 on_event: EventSink | None = None) -> None:
        self.board = board
        self.cu = cu
        self.voice = voice
        self._on_event = on_event or (lambda e: None)

    # ---- infra -------------------------------------------------------------
    def _emit(self, event: dict) -> None:
        self._on_event(event)

    def _persist(self, c: Container) -> Container:
        """Write board first, then push a board_update (invariant 4)."""
        c = self.board.upsert(c)
        self._emit(events.board_update(c))
        return c

    def _audit(self, c: Container, actor: Actor, action: str,
               target: System | None = None, artifact: str | None = None,
               result: str = "") -> Container:
        c.action_log.append(AuditEntry(ts=_now(), actor=actor, action=action,
                                       target_system=target, artifact_path=artifact,
                                       result=result))
        return self._persist(c)

    def _set_status(self, c: Container, status: ContainerStatus) -> Container:
        c.status = status
        return self._persist(c)

    # ---- reads (auto) ------------------------------------------------------
    def _read(self, c: Container, system: System, reference: str | None = None) -> Observation:
        params = {"container_id": c.id}
        if reference:
            params["reference"] = reference
        task = Task(kind=TaskKind.read, target_system=system,
                    goal=f"read {system.value} status for {c.id}",
                    params=params, cost_class=CostClass.read)
        obs = self.cu.run(task)
        assert isinstance(obs, Observation)
        self._audit(c, Actor.cu, f"read {system.value}: {obs.fields or 'nothing'}",
                    target=system, artifact=obs.screenshot_path,
                    result="clean" if not self._interpret(c, obs) else "blocker")
        return obs

    def _interpret(self, c: Container, obs: Observation) -> Blocker | None:
        """Untrusted portal text -> validated Blocker (or None if clean)."""
        f = obs.fields or {}
        if obs.source_system == System.terminal and f.get("detention_unpaid") is True:
            return Blocker(
                source_system=System.terminal, type="unpaid_detention",
                evidence=f"unpaid terminal detention ${float(f.get('amount_usd', 0)):.0f}",
                is_binding=True, discovered_via=DiscoveredVia.screen,
                reference=f.get("reference"),
            )
        if obs.source_system == System.customs and f.get("status") == "hold":
            return Blocker(
                source_system=System.customs, type="customs_hold",
                evidence=f"customs hold: {f.get('reason', 'unspecified')}",
                is_binding=True, discovered_via=DiscoveredVia.screen,
            )
        if obs.source_system == System.carrier and f.get("hold") is True:
            return Blocker(
                source_system=System.carrier, type="carrier_hold",
                evidence="carrier hold on release", is_binding=True,
                discovered_via=DiscoveredVia.screen,
            )
        return None

    # ---- transitions -------------------------------------------------------
    def begin_diagnosis(self, container_id: str, responsible: System | None = None,
                        kind: AlertKind = AlertKind.OVERDUE) -> Container:
        """monitoring -> diagnosing (shared by the deterministic path and the
        agentic path). Audits the alert and flips status; does NOT read portals."""
        c = self._require(container_id)
        self._audit(c, Actor.monitor,
                    f"{kind.value} fired (responsible={responsible.value if responsible else '-'})")
        return self._set_status(c, ContainerStatus.diagnosing)

    def on_alert(self, container_id: str, responsible: System | None,
                 kind: AlertKind = AlertKind.OVERDUE) -> Container:
        """Deterministic path: begin diagnosis, then run the hardcoded read sweep."""
        self.begin_diagnosis(container_id, responsible, kind)
        return self.diagnose(self._require(container_id), first=responsible)

    def diagnose(self, c: Container, first: System | None = None) -> Container:
        """Read the fired system, then upstream to rule out. Fuse a Blocker or
        fall to stalled_unlocatable when the cause is on no accessible portal."""
        order: list[System] = []
        if first:
            order.append(first)
        for s in _UPSTREAM:
            if s not in order:
                order.append(s)

        for system in order:
            # terminal needs the voice reference; pass it if we already hold one
            ref = self._known_reference(c) if system == System.terminal else None
            obs = self._read(c, system, reference=ref)
            blocker = self._interpret(c, obs)
            if blocker:
                return self._fuse_blocker(c, blocker)

        # nothing visible anywhere -> wait for exogenous truth (the call)
        self._audit(c, Actor.cu, "all reads clean — cause not on any accessible portal")
        return self._set_status(c, ContainerStatus.stalled_unlocatable)

    def _fuse_blocker(self, c: Container, blocker: Blocker) -> Container:
        c = self._require(c.id)  # refresh
        # If the truth first arrived by voice, the on-screen read only confirms it
        # — preserve voice provenance + reference (load-bearing for invariant 6).
        prior = next((b for b in c.blockers if b.type == blocker.type), None)
        if prior and prior.discovered_via == DiscoveredVia.voice:
            blocker.discovered_via = DiscoveredVia.voice
            blocker.reference = blocker.reference or prior.reference
        c.blockers = [b for b in c.blockers if b.type != blocker.type] + [blocker]
        label, cost = _ACTION_COPY.get(blocker.type, ("Resolve", CostClass.high))
        waiting = "Driver waiting." if any(
            b.discovered_via == DiscoveredVia.voice for b in c.blockers
        ) else "Importer waiting."
        line = f"{c.id} — binding blocker: {blocker.evidence}. {waiting}"
        action = PendingAction(action_id=f"{blocker.type}:{c.id}", container_id=c.id,
                               target_system=blocker.source_system, goal=label,
                               params={"container_id": c.id,
                                       "reference": blocker.reference or ""},
                               cost_class=cost, line=line)
        c.pending_action = action
        self._audit(c, Actor.cu, f"blocker fused: {blocker.evidence}",
                    target=blocker.source_system)
        self._set_status(c, ContainerStatus.awaiting_action)
        self._emit(events.surfaced_line(c.id, action.action_id, line, cost.value))
        logger.info("SURFACED: %s [%s]", line, label)
        return c

    def take_call_truth(self, hint: str | None = None) -> FieldTruth:
        """Run the voice channel, stream the transcript to the UI, and return the
        extracted FieldTruth (without ingesting it — the caller routes it by mode)."""
        self._emit(events.call_started(None))
        # container id is only known once the driver states it; stream transcript
        # to the UI as it arrives (unattached until we learn the id).
        heard: dict[str, str | None] = {"cid": hint}

        def _sink(speaker: str, text: str) -> None:
            self._emit(events.transcript(heard["cid"], speaker, text))

        truth = self.voice.take_call(hint=hint, on_transcript=_sink)
        heard["cid"] = truth.container_id
        return truth

    def on_call(self, hint: str | None = None) -> Container:
        """EVENT — the *pull* path (scripted demo, deterministic mode)."""
        return self.ingest_field_truth(self.take_call_truth(hint))

    def record_voice_truth(self, truth: FieldTruth) -> Container:
        """Write the voice Blocker (reference from the driver call) and flip to
        diagnosing. Shared by the deterministic and agentic push paths; does NOT
        read portals."""
        c = self._require(truth.container_id)
        self._emit(events.call_started(c.id))
        voice_blocker = Blocker(
            source_system=System.terminal, type=truth.blocker_type,
            evidence=f"driver reports {truth.blocker_type} (ref {truth.reference})",
            is_binding=True, discovered_via=DiscoveredVia.voice, reference=truth.reference,
        )
        c.blockers = [b for b in c.blockers if b.discovered_via != DiscoveredVia.voice] + [voice_blocker]
        self._audit(c, Actor.voice, f"call: {truth.blocker_type} ref={truth.reference}",
                    result=truth.raw_transcript[:200])
        return self._set_status(c, ContainerStatus.diagnosing)

    def ingest_field_truth(self, truth: FieldTruth) -> Container:
        """Deterministic path: record the voice truth, then a targeted terminal
        read WITH the reference reveals the hidden detention (invariant 6)."""
        c = self.record_voice_truth(truth)
        return self.diagnose(c, first=System.terminal)

    def mark_approved(self, container_id: str, action_id: str) -> Container:
        """Human /approve: mark the pending action approved + flip to executing.
        Does NOT run the act (the agentic path lets the agent execute; the
        deterministic `approve` runs it immediately)."""
        c = self._require(container_id)
        action = c.pending_action
        if action is None and c.status in (
            ContainerStatus.executing, ContainerStatus.verifying,
            ContainerStatus.resolving, ContainerStatus.released,
        ):
            return c  # idempotent: already approved/executing (double-click)
        if not action or action.action_id != action_id:
            raise ValueError(f"no pending action {action_id!r} for {container_id}")
        action.approved = True
        c.pending_action = action
        self._audit(c, Actor.human, f"approved: {action.goal}")
        return self._set_status(c, ContainerStatus.executing)

    def approve(self, container_id: str, action_id: str) -> Container:
        """Deterministic path: /approve -> executing -> act -> verifying -> resolving."""
        c = self.mark_approved(container_id, action_id)  # -> executing
        result = self._dispatch_act(c, c.pending_action)
        return self._on_action_result(c, result)

    def _dispatch_act(self, c: Container, action: PendingAction) -> ActionResult:
        # Gate policy (invariant 3): high actions must be pre-approved.
        if action.cost_class == CostClass.high and not action.approved:
            raise PermissionError("high-cost action dispatched without /approve")
        task = Task(kind=TaskKind.act, target_system=action.target_system,
                    goal=action.goal, params=action.params, cost_class=action.cost_class)
        result = self.cu.run(task)
        assert isinstance(result, ActionResult)
        self._audit(c, Actor.cu, f"act: {action.goal} (verified={result.verified})",
                    target=action.target_system, artifact=result.before_shot,
                    result="ok" if result.ok else "failed")
        self._audit(c, Actor.cu, f"verify re-read {action.target_system.value}",
                    target=action.target_system, artifact=result.after_shot,
                    result="verified" if result.verified else "unverified")
        return result

    def _on_action_result(self, c: Container, result: ActionResult) -> Container:
        if not (result.ok and result.verified):
            return self._set_status(c, ContainerStatus.escalated)
        c = self._require(c.id)
        c.pending_action = None
        # clear the satisfied timer for the resolved system
        for t in c.timers:
            if t.responsible_system == result.target_system and not t.satisfied:
                t.satisfied = True
                t.satisfied_by = t.satisfied_by or "gated_out"
        self._set_status(c, ContainerStatus.verifying)
        # Speak the resolution back to the driver (§9). The message is authored in
        # ENGLISH and TRANSLATED to whatever language the driver is actually speaking
        # by Gemini Live on the open call — that IS the Live Translate value. We do
        # NOT know the driver's language reliably server-side, so we never hard-code
        # it (hard-coding "es" is what made every driver hear Spanish).
        ref = self._known_reference(c) or "the gate reference"
        message = (f"The charge is paid and the container is released. "
                   f"Show reference {ref} at the gate — you can go through.")
        self.voice.callback(c.id, message, "auto")
        self._audit(c, Actor.voice, f"callback: told driver — {message}", result="auto")
        # verified pay = the container is released (final green state). Surface the
        # spoken confirmation to the Site Office so the human sees the driver was told.
        c = self._set_status(c, ContainerStatus.released)
        self._emit(events.resolved(c.id, message, "auto"))
        return c

    def dismiss(self, container_id: str, alert_id: str) -> Container:
        """awaiting_action + /dismiss -> monitoring; lower future severity."""
        c = self._require(container_id)
        c.alerts = [a for a in c.alerts if a.id != alert_id]
        c.pending_action = None
        self._audit(c, Actor.human, f"dismissed alert {alert_id}")
        return self._set_status(c, ContainerStatus.moving)

    # ---- agent tool-primitives ---------------------------------------------
    # Thin, JSON-friendly wrappers the SolverAgent's brain calls as tools. They
    # reuse the same transitions as the deterministic path, so all invariants
    # (CU-only reads, human gate, audit, durable board) hold identically.
    def tool_read_portal(self, container_id: str, system: str,
                         reference: str | None = None) -> dict:
        """Read one portal via Computer Use (auto, invariant 2). Returns the
        parsed fields + any binding blocker found (or null = clean)."""
        c = self._require(container_id)
        sys = System(system)
        ref = reference or (self._known_reference(c) if sys == System.terminal else None)
        obs = self._read(c, sys, reference=ref)
        blocker = self._interpret(c, obs)
        return {
            "system": sys.value,
            "fields": obs.fields,
            "blocker": None if blocker is None else {
                "type": blocker.type, "source_system": blocker.source_system.value,
                "evidence": blocker.evidence, "reference": blocker.reference,
            },
        }

    def tool_surface_blocker(self, container_id: str, blocker_type: str,
                             source_system: str, evidence: str,
                             reference: str | None = None) -> dict:
        """Surface a binding blocker to the human (one-tap gate). PAUSES here —
        no high-cost action runs until /approve (invariant 3)."""
        c = self._require(container_id)
        ref = reference or self._known_reference(c)
        blocker = Blocker(source_system=System(source_system), type=blocker_type,
                          evidence=evidence, is_binding=True,
                          discovered_via=DiscoveredVia.screen, reference=ref)
        c = self._fuse_blocker(c, blocker)  # -> awaiting_action + surfaced_line
        return {"status": "awaiting_human",
                "line": c.pending_action.line if c.pending_action else ""}

    def tool_mark_unlocatable(self, container_id: str, reason: str = "") -> dict:
        """No blocker on any accessible portal -> wait for exogenous (voice) truth."""
        c = self._require(container_id)
        self._audit(c, Actor.agent,
                    f"cause not on any accessible portal{f' ({reason})' if reason else ''}")
        self._set_status(c, ContainerStatus.stalled_unlocatable)
        return {"status": "stalled_unlocatable"}

    def tool_execute_approved_action(self, container_id: str) -> dict:
        """Run the approved high-cost action via CU, then verify (invariant 3:
        only reachable once a human /approve set approved=True).

        Idempotent: if the gate was already consumed (a prior execute paid it and
        the container is past the gate) this is a benign no-op, not a failure — so
        a double-click / re-spawn resolves cleanly instead of raising."""
        c = self._require(container_id)
        action = c.pending_action
        if action is None:
            if c.status in (ContainerStatus.verifying, ContainerStatus.resolving,
                            ContainerStatus.released):
                return {"ok": True, "verified": True, "status": c.status.value,
                        "already_resolved": True}
            raise PermissionError("no pending action to execute")
        if not action.approved:  # invariant 3: never pay without the human gate
            raise PermissionError("action not approved")
        result = self._dispatch_act(c, action)
        c = self._on_action_result(c, result)
        return {"ok": result.ok, "verified": result.verified, "status": c.status.value}

    # ---- helpers -----------------------------------------------------------
    def _known_reference(self, c: Container) -> str | None:
        for b in c.blockers:
            if b.reference:
                return b.reference
        return None

    def _require(self, container_id: str) -> Container:
        c = self.board.get(container_id)
        if c is None:
            raise KeyError(f"unknown container {container_id!r}")
        return c
