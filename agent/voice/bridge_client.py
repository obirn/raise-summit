"""Live speak-back Voice: the orchestrator side of the resolution callback.

`callback(...)` POSTs to the Twilio<->Gemini-Live bridge's `/speak`, which injects
the confirmation into the OPEN call so the driver HEARS it in their language via
Live Translate (§9) — not just a Site Office banner. Fire-and-forget so a down
bridge / no active call never blocks the approval path. `take_call` delegates to
the scripted stub (the live call arrives via the bridge's push path, not pull).
"""

from __future__ import annotations

import logging
import os
import threading

import httpx

from ..board.models import FieldTruth
from .base import TranscriptSink
from .stub import StubVoice

logger = logging.getLogger("voice.bridge")

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:8080")


class BridgeVoice:
    def __init__(self, bridge_url: str = BRIDGE_URL) -> None:
        self._url = bridge_url
        self._stub = StubVoice()

    def take_call(self, hint: str | None = None,
                  on_transcript: TranscriptSink | None = None) -> FieldTruth:
        return self._stub.take_call(hint, on_transcript)

    def callback(self, container_id: str, message: str, lang: str) -> None:
        def _post() -> None:
            try:
                httpx.post(f"{self._url}/speak", json={
                    "container_id": container_id, "message": message, "lang": lang,
                }, timeout=5.0)
            except Exception as exc:  # noqa: BLE001 — never break approval on a down bridge
                logger.warning("speak-back to bridge failed (call over?): %s", exc)

        threading.Thread(target=_post, daemon=True).start()
        logger.info("[callback->bridge %s/%s] %s", container_id, lang, message)
