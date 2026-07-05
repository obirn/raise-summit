"""M5 — agentic layer (solver agents) with the offline ScriptedBrain."""

from __future__ import annotations

import pytest

from agent.board.board import Board
from agent.board.models import AgentStatus, ContainerStatus, FieldTruth, System
from agent.computer_use.stub import StubComputerUse
from agent.orchestrator.engine import Engine
from agent.solver.manager import AgentManager
from agent.voice.stub import StubVoice
from seed.scenario import DEMO_NOW, seed_board


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    board = Board(env_id="test", db_path=str(tmp_path / "board.db"))
    seed_board(board, DEMO_NOW)
    engine = Engine(board, StubComputerUse(), StubVoice())
    mgr = AgentManager(engine, lambda e: None, brain_kind="scripted")
    return engine, mgr, str(tmp_path / "board.db")


def test_agentic_golden_path(setup):
    engine, mgr, _ = setup

    # alert -> agent plans reads -> nothing on any portal -> stalled_unlocatable
    engine.begin_diagnosis("MSKU4471", System.terminal)
    c = mgr.spawn("MSKU4471", hint_system="terminal", background=False)
    assert c.status == ContainerStatus.stalled_unlocatable
    assert c.agent.status == AgentStatus.done
    assert [s.tool for s in c.agent.steps].count("read_portal") == 4  # terminal/tms/carrier/customs

    # voice truth -> new agent reads terminal WITH ref -> surfaces $340 -> gate
    engine.record_voice_truth(FieldTruth(container_id="MSKU4471",
                                         blocker_type="unpaid_detention", reference="DET-4471-B"))
    c = mgr.spawn("MSKU4471", hint_system="terminal", background=False)
    assert c.status == ContainerStatus.awaiting_action
    assert c.agent.status == AgentStatus.awaiting_human
    assert "$340" in c.pending_action.line and "Driver waiting" in c.pending_action.line

    # approve -> agent resumes -> executes -> resolving
    engine.mark_approved("MSKU4471", c.pending_action.action_id)
    c = mgr.resume_after_approve("MSKU4471", background=False)
    assert c.status == ContainerStatus.released
    assert c.agent.status == AgentStatus.done
    assert any(s.tool == "execute_approved_action" for s in c.agent.steps)


def test_agentic_decoy_screen_only(setup):
    """TCLU3380: the agent reads the responsible portal (customs), finds the HS-code
    hold on screen, and surfaces it — no voice needed."""
    engine, mgr, _ = setup
    engine.begin_diagnosis("TCLU3380", System.customs)
    c = mgr.spawn("TCLU3380", hint_system="customs", background=False)
    assert c.status == ContainerStatus.awaiting_action
    assert c.agent.status == AgentStatus.awaiting_human
    assert "customs hold" in c.pending_action.line


def test_agent_resume_lossless_mid_gate(setup, tmp_path, monkeypatch):
    """Kill after the agent surfaces (awaiting_human); resume from disk; the agent
    state is intact and approve -> resume still reaches resolving."""
    engine, mgr, db = setup
    engine.record_voice_truth(FieldTruth(container_id="MSKU4471",
                                         blocker_type="unpaid_detention", reference="DET-4471-B"))
    before = mgr.spawn("MSKU4471", hint_system="terminal", background=False)
    assert before.agent.status == AgentStatus.awaiting_human

    # simulate a process restart: fresh board/engine/manager from the same DB
    board2 = Board.resume("test", db)
    after = board2.get("MSKU4471")
    assert after.model_dump(mode="json") == before.model_dump(mode="json")  # nothing lost

    engine2 = Engine(board2, StubComputerUse(), StubVoice())
    mgr2 = AgentManager(engine2, lambda e: None, brain_kind="scripted")
    engine2.mark_approved("MSKU4471", after.pending_action.action_id)
    c = mgr2.resume_after_approve("MSKU4471", background=False)
    assert c.status == ContainerStatus.released
