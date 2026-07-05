"""SolverAgent — one durable agent working one stuck container.

Runs the brain's tool loop against the engine's tool-primitives (which use
Computer Use). Every step is persisted to `Container.agent` (AgentState) so the
run is resumable by agent_id — the "Antigravity" capability. The agent pauses at
the human gate (surface_blocker) and resumes on /approve to execute the fix.

Concurrency: the brain call (LLM) runs outside the shared lock (agents reason in
parallel); the engine tool call + state persist run under the lock (board writes
and the single browser serialize).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable

from ..board.board import Board
from ..board.models import AgentState, AgentStatus, AgentStep, Container
from ..orchestrator import events
from .brain import Brain, BrainContext, ToolCall

logger = logging.getLogger("solver.agent")

# tool -> resulting agent status; presence here means the loop stops after it.
_TERMINAL_STATUS = {
    "surface_blocker": AgentStatus.awaiting_human,
    "mark_unlocatable": AgentStatus.done,
    "execute_approved_action": AgentStatus.done,
    "done": AgentStatus.done,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SolverAgent:
    def __init__(self, engine, brain: Brain, agent_id: str, container_id: str,
                 lock: threading.Lock, on_event: Callable[[dict], None],
                 brain_kind: str = "scripted", hint_system: str | None = None,
                 max_steps: int = 12) -> None:
        self.engine = engine
        self.brain = brain
        self.agent_id = agent_id
        self.container_id = container_id
        self.lock = lock
        self._emit = on_event
        self.brain_kind = brain_kind
        self.hint_system = hint_system
        self.max_steps = max_steps

    # ---- board helpers -----------------------------------------------------
    def _board(self) -> Board:
        return self.engine.board

    def _get(self) -> Container:
        return self.engine._require(self.container_id)

    def _held_state(self, c: Container) -> dict:
        return {
            "id": c.id, "status": c.status.value,
            "dollars_at_risk": c.free_time.dollars_at_risk if c.free_time else 0.0,
            "blockers": [{"type": b.type, "reference": b.reference,
                          "discovered_via": b.discovered_via.value} for b in c.blockers],
            "known_reference": self.engine._known_reference(c),
            "hint_system": self.hint_system,
            "pending_action": bool(c.pending_action),
        }

    def ensure_state(self, goal: str) -> None:
        with self.lock:
            c = self._get()
            if c.agent is None or c.agent.agent_id != self.agent_id:
                c.agent = AgentState(agent_id=self.agent_id, container_id=c.id,
                                     goal=goal, brain=self.brain_kind,
                                     status=AgentStatus.planning)
                self._board().upsert(c)
        self._emit(events.agent_spawned(self.container_id, self.agent_id, goal, self.brain_kind))

    # ---- the loop ----------------------------------------------------------
    def run(self, phase: str = "plan", goal: str = "") -> Container:
        self.ensure_state(goal)
        for _ in range(self.max_steps):
            c = self._get()
            if phase == "execute":
                # Post-approval: the human already chose the action — there is
                # nothing left to reason about, so we DON'T ask the LLM brain
                # (which has no signal that /approve happened and would answer
                # `done`/re-surface, leaving the gate stuck). Carry out the
                # approved fix deterministically for every brain. CU still clicks.
                call = self._execute_phase_action(c)
            else:
                ctx = BrainContext(
                    container_id=self.container_id, goal=c.agent.goal if c.agent else goal,
                    phase=phase, held_state=self._held_state(c),
                    steps=[{"tool": s.tool, "args": s.args, "result": s.result}
                           for s in (c.agent.steps if c.agent else [])],
                    # durable Antigravity handles (resume the SAME server-side reasoning)
                    previous_interaction_id=c.agent.previous_interaction_id if c.agent else None,
                    environment_id=c.agent.environment_id if c.agent else None,
                    pending_call_id=c.agent.pending_call_id if c.agent else None,
                )
                call = self.brain.next_action(ctx)      # LLM / FSM — outside lock
            with self.lock:
                result, terminal_status = self._exec(call)
                self._record(call, result, terminal_status)
            summary = self._summary(call, result)
            self._emit(events.agent_step(self.container_id, self.agent_id, call.name,
                                         summary, (terminal_status or AgentStatus.planning).value,
                                         interaction_id=call.interaction_id))
            if terminal_status is not None:
                self._emit(events.agent_done(self.container_id, self.agent_id,
                                             terminal_status.value))
                break
        return self._get()

    def _execute_phase_action(self, c: Container) -> ToolCall:
        """Deterministic post-approval sequence: run the approved action once,
        then finish. Independent of the brain so the human gate never stalls."""
        steps = c.agent.steps if c.agent else []
        if not any(s.tool == "execute_approved_action" for s in steps):
            return ToolCall("execute_approved_action", {})
        return ToolCall("done", {"summary": "resolved"})

    def _exec(self, call: ToolCall) -> tuple[dict, AgentStatus | None]:
        n, a = call.name, call.args
        try:
            if n == "read_portal":
                result = self.engine.tool_read_portal(self.container_id, a["system"], a.get("reference"))
            elif n == "surface_blocker":
                result = self.engine.tool_surface_blocker(
                    self.container_id, a["blocker_type"], a["source_system"],
                    a["evidence"], a.get("reference"))
            elif n == "mark_unlocatable":
                result = self.engine.tool_mark_unlocatable(self.container_id, a.get("reason", ""))
            elif n == "execute_approved_action":
                result = self.engine.tool_execute_approved_action(self.container_id)
            elif n == "done":
                result = {"summary": a.get("summary", "")}
            else:
                result = {"error": f"unknown tool {n}"}
        except Exception as e:  # noqa: BLE001 — a bad step fails the agent, not the process
            logger.exception("agent %s tool %s failed", self.agent_id, n)
            return {"error": str(e)}, AgentStatus.failed
        return result, _TERMINAL_STATUS.get(n)

    def _record(self, call: ToolCall, result: dict, terminal_status: AgentStatus | None) -> None:
        c = self._get()
        if c.agent is None:
            c.agent = AgentState(agent_id=self.agent_id, container_id=c.id, brain=self.brain_kind)
        c.agent.steps.append(AgentStep(ts=_now(), tool=call.name, args=call.args,
                                       result=result, summary=self._summary(call, result)))
        c.agent.status = terminal_status or AgentStatus.planning
        # persist the durable Antigravity handles so a resumed process continues
        # the SAME server-side interaction by id (load-bearing durability).
        if call.interaction_id is not None:
            c.agent.previous_interaction_id = call.interaction_id
        if call.environment_id is not None:
            c.agent.environment_id = call.environment_id
        c.agent.pending_call_id = call.call_id
        self._board().upsert(c)

    def _summary(self, call: ToolCall, result: dict) -> str:
        if call.name == "read_portal":
            blk = result.get("blocker")
            return f"read {call.args.get('system')}: " + (blk["evidence"] if blk else "clean")
        if call.name == "surface_blocker":
            return f"surfaced: {call.args.get('evidence')}"
        if call.name == "mark_unlocatable":
            return "cause on no accessible portal — awaiting driver call"
        if call.name == "execute_approved_action":
            return f"executed fix (verified={result.get('verified')})"
        return call.args.get("summary", call.name)
