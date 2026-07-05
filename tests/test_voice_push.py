"""M3 — the real-telephony *push* path, exercised WITHOUT a phone.

Sets a temp board DB before importing the orchestrator app so it seeds fresh.
"""

from __future__ import annotations

import os
import tempfile

os.environ["BOARD_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ARTIFACTS_DIR"] = tempfile.mkdtemp()
os.environ["CU_MODE"] = "stub"

from starlette.testclient import TestClient  # noqa: E402

import agent.orchestrator.app as app_mod  # noqa: E402
from agent.voice import twilio_bridge  # noqa: E402


def test_field_truth_push_drives_awaiting_action():
    """POST /events/field-truth (what the Twilio bridge fires on the model's
    tool-call) reveals the $340 detention and surfaces the one-tap gate."""
    client = TestClient(app_mod.app)
    assert any(c["id"] == "MSKU4471" for c in client.get("/board").json())

    r = client.post("/events/field-truth",
                    json={"container_id": "MSKU4471", "reference": "DET-4471-B"})
    assert r.status_code == 202

    msku = next(c for c in client.get("/board").json() if c["id"] == "MSKU4471")
    assert msku["status"] == "awaiting_action"
    assert "$340" in msku["pending_action"]["line"]
    assert any(b["discovered_via"] == "voice" for b in msku["blockers"])


def test_bridge_voice_returns_twiml_stream():
    """The bridge answers an inbound call with TwiML that opens the media stream."""
    client = TestClient(twilio_bridge.app)
    r = client.post("/voice", headers={"host": "example.ngrok.app"})
    assert r.status_code == 200
    assert '<Stream url="wss://example.ngrok.app/ws"' in r.text
