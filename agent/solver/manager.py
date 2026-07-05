"""AgentManager — the orchestrator's agent factory (the "creates agents" part).

Spawns one durable SolverAgent per stuck container and resumes it after the human
gate. Agents run in their own threads (parallel portfolio); a single shared lock
serializes board writes + the single browser, while the brains (LLM) reason
concurrently. `background=False` runs synchronously for tests.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from ..board.models import AgentStatus, Container
from .agent import SolverAgent
from .brain import make_brain

logger = logging.getLogger("solver.manager")

_ACTIVE = {AgentStatus.planning, AgentStatus.executing}


class AgentManager:
    def __init__(self, engine, on_event: Callable[[dict], None],
                 brain_kind: str = "scripted") -> None:
        self.engine = engine
        self._emit = on_event
        self.brain_kind = brain_kind
        self.board_lock = threading.Lock()   # shared by all agents (board + browser)
        self.threads: dict[str, threading.Thread] = {}
        self._counter = 0

    def _next_id(self, container_id: str) -> str:
        self._counter += 1
        return f"agent-{container_id}-{self._counter}"

    def _busy(self, container_id: str) -> bool:
        t = self.threads.get(container_id)
        if t and t.is_alive():
            return True
        c = self.engine.board.get(container_id)
        return bool(c and c.agent and c.agent.status in _ACTIVE and t and t.is_alive())

    # ---- spawn (plan phase) ------------------------------------------------
    def spawn(self, container_id: str, hint_system: str | None = None,
              goal: str = "", background: bool = True) -> Container | None:
        if background and self._busy(container_id):
            logger.info("agent already active for %s — skip spawn", container_id)
            return None
        agent = self._make(self._next_id(container_id), container_id, hint_system)
        goal = goal or f"Unblock stuck container {container_id}"
        return self._launch(container_id, agent, "plan", goal, background)

    # ---- resume (execute phase, after human /approve) ----------------------
    def resume_after_approve(self, container_id: str, background: bool = True) -> Container | None:
        c = self.engine.board.get(container_id)
        # Idempotent gate: if the action was already executed (double-click, or an
        # execute agent is still finishing) don't spawn a second executor.
        if c is None or c.pending_action is None:
            logger.info("resume_after_approve: no pending action for %s — skip", container_id)
            return c
        t = self.threads.get(container_id)
        if background and t and t.is_alive():
            logger.info("resume_after_approve: agent already running for %s — skip", container_id)
            return c
        agent_id = c.agent.agent_id if (c and c.agent) else self._next_id(container_id)
        agent = self._make(agent_id, container_id, hint_system=None)
        goal = (c.agent.goal if (c and c.agent) else "") or f"Unblock stuck container {container_id}"
        return self._launch(container_id, agent, "execute", goal, background)

    # ---- internals ---------------------------------------------------------
    def _make(self, agent_id: str, container_id: str, hint_system: str | None) -> SolverAgent:
        return SolverAgent(self.engine, make_brain(self.brain_kind), agent_id, container_id,
                           self.board_lock, self._emit, brain_kind=self.brain_kind,
                           hint_system=hint_system)

    def _launch(self, container_id: str, agent: SolverAgent, phase: str, goal: str,
                background: bool) -> Container | None:
        if not background:
            return agent.run(phase=phase, goal=goal)
        t = threading.Thread(target=agent.run, kwargs={"phase": phase, "goal": goal},
                             daemon=True, name=f"solver-{container_id}")
        self.threads[container_id] = t
        t.start()
        return None
