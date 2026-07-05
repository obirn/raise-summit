"""Probe the experimental Gemini Interactions/Agents API — is the managed
`antigravity-preview-05-2026` agent reachable with our key?

This decides whether an `AntigravityBrain` (real managed agent) is worth wiring.
Our solver agents do NOT depend on this — they use our own function-calling brain
+ our local Computer Use. Read-only-ish (may create one background interaction).

Usage: python scripts/antigravity_probe.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

AGENT = "antigravity-preview-05-2026"


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — skipping Antigravity probe.")
        return 0
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print("1) Does the SDK expose the Interactions/Agents surface?")
    for attr in ("interactions", "agents"):
        print(f"   client.{attr}:", "yes" if hasattr(client, attr) else "NO")

    print(f"2) Trying client.interactions.create(agent={AGENT!r}, environment={{'type':'remote'}}) ...")
    try:
        res = client.interactions.create(  # type: ignore[attr-defined]
            agent=AGENT,
            input="Say the single word: ready.",
            environment={"type": "remote"},
            store=True,
            background=True,
        )
        iid = getattr(res, "id", None)
        print("   OK — interaction created:", iid or res)
        print("   => AntigravityBrain is VIABLE (pin google-genai==2.10.0; the managed agent runs "
              "in a remote sandbox, so our localhost portals would need a public URL).")
        return 0
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        reachable = "environment" not in msg.lower()  # a shape error still means the API answered
        print(f"   {type(e).__name__}: {msg}")
        print("   => API is reachable" if "invalid_request" in msg or "400" in msg
              else "   => not usable with this key")
        print("   Our solver agents don't depend on this — GeminiFunctionCallingBrain already works.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
