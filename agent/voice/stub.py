"""DEMO-ONLY Live Translate fallback (M1/M3 safety net).

Deterministic two-way dialogue: a scripted Spanish driver at the terminal gate,
the agent replying in Spanish and extracting the exact reference DET-4471-B. This
is the load-bearing point of invariant 6 — the reference exists ONLY in the
driver's voice, on no monitored portal. M3 swaps this for the real Twilio<->
Gemini-Live bridge; the scripted track (seed/driver_es.wav) keeps the judge demo
independent of live mic quality.
"""

from __future__ import annotations

import logging

from ..board.models import FieldTruth
from .base import TranscriptSink

logger = logging.getLogger("voice.stub")

# Scripted ES<->EN two-way transcript (speaker, es, en).
SCRIPT: list[tuple[str, str, str]] = [
    ("driver", "Hola, estoy en la puerta del terminal con el contenedor MSKU4471 y no me dejan salir.",
     "Hi, I'm at the terminal gate with container MSKU4471 and they won't let me out."),
    ("agent", "Entendido. ¿Le muestran algún número de referencia o de factura en la pantalla?",
     "Understood. Are they showing you a reference or invoice number on the screen?"),
    ("driver", "Sí, dice detención pendiente, referencia DET guión 4471 guión B.",
     "Yes, it says pending detention, reference DET-4471-B."),
    ("agent", "Perfecto, DET-4471-B. Lo reviso ahora mismo y le llamo en cuanto esté resuelto.",
     "Perfect, DET-4471-B. I'll check it right now and call you back as soon as it's resolved."),
]


class StubVoice:
    def take_call(self, hint: str | None = None,
                  on_transcript: TranscriptSink | None = None) -> FieldTruth:
        transcript_lines: list[str] = []
        for speaker, es, en in SCRIPT:
            line = f"[{speaker}] {es}  ({en})"
            transcript_lines.append(line)
            logger.info(line)
            if on_transcript:
                on_transcript(speaker, f"{es}  ({en})")
        return FieldTruth(
            container_id="MSKU4471",
            blocker_type="unpaid_detention",
            reference="DET-4471-B",
            raw_transcript="\n".join(transcript_lines),
            lang="es",
        )

    def callback(self, container_id: str, message: str, lang: str) -> None:
        logger.info("[callback %s/%s] %s", container_id, lang, message)
