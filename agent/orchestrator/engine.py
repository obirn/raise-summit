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
    def on_alert(self, container_id: str, responsible: System | None,
                 kind: AlertKind = AlertKind.OVERDUE) -> Container:
        """monitoring -> diagnosing: dispatch a read to the responsible system."""
        c = self._require(container_id)
        self._audit(c, Actor.monitor, f"{kind.value} fired (responsible={responsible.value if responsible else '-'})")
        self._set_status(c, ContainerStatus.diagnosing)
        return self.diagnose(c, first=responsible)

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

    def on_call(self, hint: str | None = None) -> Container:
        """EVENT — the *pull* path (scripted demo). Ask the voice channel for the
        FieldTruth, then ingest it. The real telephony bridge uses the *push*
        path (`ingest_field_truth`) instead; both converge on the same logic."""
        self._emit(events.call_started(None))
        # container id is only known once the driver states it; stream transcript
        # to the UI as it arrives (unattached until we learn the id).
        heard: dict[str, str | None] = {"cid": hint}

        def _sink(speaker: str, text: str) -> None:
            self._emit(events.transcript(heard["cid"], speaker, text))

        truth = self.voice.take_call(hint=hint, on_transcript=_sink)
        heard["cid"] = truth.container_id
        return self.ingest_field_truth(truth)

    def ingest_field_truth(self, truth: FieldTruth) -> Container:
        """EVENT — the *push* entrypoint. Given a FieldTruth (from the scripted
        stub OR a real driver call via the Twilio bridge), write the voice Blocker
        and run a targeted terminal read WITH the reference, which reveals the
        hidden detention on screen (invariant 6)."""
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
        self._set_status(c, ContainerStatus.diagnosing)
        # targeted read with the reference now reveals the detention on screen
        return self.diagnose(c, first=System.terminal)

    def approve(self, container_id: str, action_id: str) -> Container:
        """awaiting_action + /approve -> executing -> verifying -> resolving."""
        c = self._require(container_id)
        action = c.pending_action
        if not action or action.action_id != action_id:
            raise ValueError(f"no pending action {action_id!r} for {container_id}")
        action.approved = True
        c.pending_action = action
        self._audit(c, Actor.human, f"approved: {action.goal}")
        self._set_status(c, ContainerStatus.executing)
        result = self._dispatch_act(c, action)
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
        # speak the resolution back in the driver's language (§9). DEMO-ONLY: the
        # scripted driver is Spanish; M3 carries FieldTruth.lang through instead.
        self.voice.callback(c.id, "ya está pagado, muestra DET-4471-B, ya puedes pasar.", "es")
        self._audit(c, Actor.voice, "callback: resolution spoken to driver", result="es")
        c = self._set_status(c, ContainerStatus.resolving)
        self._emit(events.resolved(c.id))
        return c

    def dismiss(self, container_id: str, alert_id: str) -> Container:
        """awaiting_action + /dismiss -> monitoring; lower future severity."""
        c = self._require(container_id)
        c.alerts = [a for a in c.alerts if a.id != alert_id]
        c.pending_action = None
        self._audit(c, Actor.human, f"dismissed alert {alert_id}")
        return self._set_status(c, ContainerStatus.moving)

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
