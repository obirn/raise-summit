"""M6 — Antigravity Interactions API as the load-bearing durable brain.

Uses a FakeInteractions client (stands in for Google's server-side durable agent)
so the whole load-bearing mechanism — reasoning seated in an interaction, resumed
by id with NO history resent — is proven offline.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest

from agent.board.board import Board
from agent.board.models import AgentStatus, ContainerStatus, FieldTruth
from agent.computer_use.stub import StubComputerUse
from agent.orchestrator.engine import Engine
from agent.solver.brain import AntigravityBrain, BrainContext, ScriptedBrain
from agent.solver.manager import AgentManager
from agent.voice.stub import StubVoice
from seed.scenario import DEMO_NOW, seed_board


class FakeInteractions:
    """A scripted stand-in for `client.interactions` that persists across our
    'process restart' (it IS the server). Decides the next function_call from the
    last function_result it was handed — reproducing the golden path."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._ids = itertools.count(1)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        iid = f"ix-{next(self._ids)}"
        env = kwargs.get("environment")
        env_id = env if isinstance(env, str) else "env-1"
        name, args = self._decide(kwargs.get("input"))
        fc = SimpleNamespace(type="function_call", name=name, arguments=args, id=f"call-{iid}")
        return SimpleNamespace(status="requires_action", id=iid, environment_id=env_id,
                               steps=[fc], output_text="")

    def get(self, id=None):  # never in_progress in the fake
        return SimpleNamespace(status="requires_action", id=id, environment_id="env-1",
                               steps=[], output_text="")

    def _decide(self, inp):
        if isinstance(inp, str):                    # fresh interaction
            return "read_portal", {"system": "terminal", "reference": "DET-4471-B"}
        last = (inp[0].get("result") or {}) if inp else {}
        if last.get("blocker"):
            b = last["blocker"]
            return "surface_blocker", {"blocker_type": b["type"], "source_system": b["source_system"],
                                       "evidence": b["evidence"], "reference": b.get("reference") or ""}
        if last.get("status") == "awaiting_human":
            return "execute_approved_action", {}
        return "done", {"summary": "done"}


class FakeClient:
    def __init__(self) -> None:
        self.interactions = FakeInteractions()


def _setup(tmp_path, monkeypatch, fake):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr("agent.solver.manager.make_brain",
                        lambda kind: AntigravityBrain(client=fake, poll_interval=0))
    db = str(tmp_path / "board.db")
    board = Board(env_id="test", db_path=db)
    seed_board(board, DEMO_NOW)
    return db, board


def test_antigravity_load_bearing_resume_by_id(tmp_path, monkeypatch):
    fake = FakeClient()
    db, board = _setup(tmp_path, monkeypatch, fake)
    eng = Engine(board, StubComputerUse(), StubVoice())
    mgr = AgentManager(eng, lambda e: None, brain_kind="antigravity")

    # voice truth -> agent reasons INSIDE an interaction -> reads terminal -> surfaces
    eng.record_voice_truth(FieldTruth(container_id="MSKU4471",
                                      blocker_type="unpaid_detention", reference="DET-4471-B"))
    c = mgr.spawn("MSKU4471", hint_system="terminal", background=False)
    assert c.status == ContainerStatus.awaiting_action
    assert c.agent.status == AgentStatus.awaiting_human
    # the agent's reasoning now lives in a durable interaction (not just our board)
    assert c.agent.previous_interaction_id is not None
    assert c.agent.environment_id == "env-1"
    prev_id = c.agent.previous_interaction_id

    # continuation calls pass previous_interaction_id and DO NOT resend history
    cont = [k for k in fake.interactions.calls if k.get("previous_interaction_id")]
    assert cont, "expected the interaction to be continued by id"
    for k in cont:
        assert isinstance(k["input"], list) and k["input"][0]["type"] == "function_result"
        assert k.get("environment") == "env-1"  # sandbox reused, not re-spun

    # --- simulate a full process restart: only the board (handles) survives ---
    board2 = Board.resume("test", db)
    after = board2.get("MSKU4471")
    assert after.agent.previous_interaction_id == prev_id  # the ONLY thing that carries the reasoning
    eng2 = Engine(board2, StubComputerUse(), StubVoice())
    mgr2 = AgentManager(eng2, lambda e: None, brain_kind="antigravity")

    # human approves -> resumed agent continues the SAME server-side interaction by id
    eng2.mark_approved("MSKU4471", after.pending_action.action_id)
    c = mgr2.resume_after_approve("MSKU4471", background=False)
    assert c.status == ContainerStatus.resolving
    assert c.agent.status == AgentStatus.done


def test_antigravity_falls_back_when_api_errors(monkeypatch):
    """If the Interactions API errors, the brain degrades gracefully (never stalls)."""
    class Raises:
        class interactions:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("interactions unavailable")
    brain = AntigravityBrain(client=Raises())
    brain._fallback_brain = ScriptedBrain()  # inject offline fallback (no API key needed)
    ctx = BrainContext(container_id="MSKU4471", goal="x", phase="plan",
                       held_state={"hint_system": "terminal", "known_reference": "DET-4471-B"},
                       steps=[])
    call = brain.next_action(ctx)
    assert call.name == "read_portal"  # produced by the fallback ScriptedBrain
