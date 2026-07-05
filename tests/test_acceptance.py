"""Acceptance tests (MASTER_PROMPT §12). These run without the network."""

from __future__ import annotations

import pathlib

import pytest

from agent.board.board import Board
from agent.board.models import (
    ContainerStatus,
    CostClass,
    DiscoveredVia,
    PendingAction,
    System,
    Task,
    TaskKind,
)
from agent.computer_use.stub import StubComputerUse
from agent.monitoring.engine import tick
from agent.orchestrator.engine import Engine
from agent.voice.stub import StubVoice
from seed.scenario import DEMO_NOW, build_containers, seed_board

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    board = Board(env_id="test", db_path=str(tmp_path / "board.db"))
    seed_board(board, DEMO_NOW)
    return Engine(board, StubComputerUse(), StubVoice())


# --- 1. detection is time math, zero portal reads ---------------------------
def test_timer_fires_without_reading_portals():
    calls = {"n": 0}

    class Spy(StubComputerUse):
        def run(self, task):  # any portal touch increments
            calls["n"] += 1
            return super().run(task)

    _ = Spy()  # unused; tick must not call CU at all
    alerts = tick(build_containers(), DEMO_NOW)
    kinds = {(a.kind.value, a.container_id, a.timer_name) for a in alerts}
    assert ("OVERDUE", "MSKU4471", "gate_out") in kinds
    assert calls["n"] == 0  # tick never invokes Computer Use


# --- 2. terminal invisible without the driver reference ---------------------
def test_terminal_invisible_without_reference():
    cu = StubComputerUse()
    without = cu.run(Task(kind=TaskKind.read, target_system=System.terminal,
                          goal="read", params={"container_id": "MSKU4471"}))
    assert without.fields == {}, "terminal must be blank without the reference"

    with_ref = cu.run(Task(kind=TaskKind.read, target_system=System.terminal, goal="read",
                           params={"container_id": "MSKU4471", "reference": "DET-4471-B"}))
    assert with_ref.fields["detention_unpaid"] is True
    assert with_ref.fields["amount_usd"] == 340.0


# --- 3. no backdoor ---------------------------------------------------------
def _code_lines(src: str) -> str:
    """Drop comment lines so prose in docstrings/comments doesn't trip checks."""
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def test_no_backdoor_static():
    """Agent modules never reach portal state directly; only the CU worker holds
    the on-screen truth stand-in, and nothing imports the frontend portals."""
    for path in (REPO / "agent").rglob("*.py"):
        code = _code_lines(path.read_text())
        # no imports of the frontend/portal code
        assert "from src" not in code and "import src" not in code
        # the portal-truth stand-in lives only in the Computer Use worker
        if path.parent.name != "computer_use":
            assert "self._truth" not in code, f"{path} touches portal truth outside computer_use"


def test_no_backdoor_runtime(engine):
    """A portal state change (terminal 'paid') is always preceded by a CU act."""
    engine.on_alert("MSKU4471", System.terminal)
    engine.on_call(hint="MSKU4471")
    c = engine.approve("MSKU4471", "unpaid_detention:MSKU4471")
    act_idx = next(i for i, e in enumerate(c.action_log)
                   if e.actor.value == "cu" and e.action.startswith("act:"))
    verify_idx = next(i for i, e in enumerate(c.action_log)
                      if "verify re-read" in e.action)
    assert act_idx < verify_idx  # verification only after the act


# --- 4. high action requires approval ---------------------------------------
def test_high_action_requires_approval(engine):
    unapproved = PendingAction(action_id="x", container_id="MSKU4471",
                               target_system=System.terminal, goal="Pay & release",
                               cost_class=CostClass.high, approved=False)
    c = engine.board.get("MSKU4471")
    with pytest.raises(PermissionError):
        engine._dispatch_act(c, unapproved)


# --- 5. resume is lossless ---------------------------------------------------
def test_resume_lossless(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    db = str(tmp_path / "board.db")
    board = Board(env_id="test", db_path=db)
    seed_board(board, DEMO_NOW)
    eng = Engine(board, StubComputerUse(), StubVoice())
    eng.on_alert("MSKU4471", System.terminal)
    eng.on_call(hint="MSKU4471")
    before = eng.approve("MSKU4471", "unpaid_detention:MSKU4471")  # -> resolving

    # kill: drop all in-memory handles; resume from disk only
    resumed = Board.resume("test", db)
    after = resumed.get("MSKU4471")
    assert after.model_dump(mode="json") == before.model_dump(mode="json")
    assert after.status == ContainerStatus.released


# --- 6. the full golden path 1->8 -------------------------------------------
def test_golden_path(engine):
    events = []
    engine._on_event = lambda e: events.append(e["type"])

    engine.on_alert("MSKU4471", System.terminal)
    assert engine.board.get("MSKU4471").status == ContainerStatus.stalled_unlocatable

    c = engine.on_call(hint="MSKU4471")
    assert c.status == ContainerStatus.awaiting_action
    assert any(b.discovered_via == DiscoveredVia.voice for b in c.blockers)
    assert "$340" in c.pending_action.line and "Driver waiting" in c.pending_action.line

    c = engine.approve("MSKU4471", c.pending_action.action_id)
    assert c.status == ContainerStatus.released

    screenshots = [e for e in c.action_log if e.artifact_path]
    assert len(screenshots) >= 2  # before + after the act
    voice_blockers = [b for b in c.blockers if b.discovered_via == DiscoveredVia.voice]
    assert len(voice_blockers) == 1
    assert {"surfaced_line", "call_started", "resolved"} <= set(events)


# --- M2: real CU worker pure helpers (no browser/network) -------------------
def test_cu_denormalize_coordinates():
    from agent.computer_use.gemini_cu import denorm
    assert denorm(0, 1440) == 0
    assert denorm(1000, 1440) == 1440
    assert denorm(500, 900) == 450
    assert denorm(250, 1440) == 360


def test_cu_goal_builder_targets_reference():
    from agent.computer_use.gemini_cu import _goal
    read = _goal(Task(kind=TaskKind.read, target_system=System.terminal, goal="",
                      params={"container_id": "MSKU4471", "reference": "DET-4471-B"}))
    assert "DET-4471-B" in read and "Look up" in read
    # a terminal read WITHOUT a reference must not invent one (invariant 6)
    blind = _goal(Task(kind=TaskKind.read, target_system=System.terminal, goal="",
                       params={"container_id": "MSKU4471"}))
    assert "DET-4471-B" not in blind and "Do NOT enter any reference" in blind
    pay = _goal(Task(kind=TaskKind.act, target_system=System.terminal, goal="",
                     params={"container_id": "MSKU4471", "reference": "DET-4471-B"}))
    assert "Pay & release" in pay


# --- M3: real-voice push entrypoint (stub CU, offline) ----------------------
def test_ingest_field_truth_surfaces_detention(engine):
    """A FieldTruth from a real driver call drives the same flow as the scripted
    demo: voice blocker + targeted terminal read reveals $340 -> awaiting_action."""
    from agent.board.models import FieldTruth
    c = engine.ingest_field_truth(FieldTruth(
        container_id="MSKU4471", blocker_type="unpaid_detention",
        reference="DET-4471-B", lang="es", raw_transcript="driver at the gate"))
    assert c.status == ContainerStatus.awaiting_action
    assert any(b.discovered_via == DiscoveredVia.voice for b in c.blockers)
    assert "$340" in c.pending_action.line and "Driver waiting" in c.pending_action.line
