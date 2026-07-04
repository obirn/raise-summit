"""Live Translate voice contract (MASTER_PROMPT §3/§9).

`take_call(hint?) -> FieldTruth` runs a two-way dialogue and returns the extracted
truth (the exact gate reference). `callback(...)` speaks the resolution back in the
driver's language. The orchestrator depends only on this interface; the M1 demo
fallback and the M3 real Twilio<->Gemini-Live bridge are interchangeable.
"""

from __future__ import annotations

from typing import Callable, Protocol

from ..board.models import FieldTruth

TranscriptSink = Callable[[str, str], None]  # (speaker, text)


class Voice(Protocol):
    def take_call(self, hint: str | None = None,
                  on_transcript: TranscriptSink | None = None) -> FieldTruth: ...

    def callback(self, container_id: str, message: str, lang: str) -> None: ...
