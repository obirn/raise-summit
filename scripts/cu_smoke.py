"""Live Computer Use smoke test — ONE real read against the terminal portal.

Proves the Gemini CU model actually drives the browser (types DET-4471-B, clicks
Look up) and that we parse the $340 detention off the rendered page.

Prereqs: GEMINI_API_KEY set, the Vite dev server running (`make demo` or
`npm run dev`), and a display (DISPLAY). Usage:  python scripts/cu_smoke.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from agent.board.models import CostClass, System, Task, TaskKind
from agent.computer_use.gemini_cu import PORTAL_BASE_URL, RealComputerUse

load_dotenv()


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — skipping live CU smoke.")
        return 0
    print(f"Portal base: {PORTAL_BASE_URL} (make sure the Vite server is up)")
    cu = RealComputerUse()
    try:
        obs = cu.run(Task(kind=TaskKind.read, target_system=System.terminal,
                          goal="read terminal detention for MSKU4471",
                          params={"container_id": "MSKU4471", "reference": "DET-4471-B"},
                          cost_class=CostClass.read))
        print("fields:", obs.fields)
        print("screenshot:", obs.screenshot_path)
        ok = obs.fields.get("detention_unpaid") is True and obs.fields.get("amount_usd") == 340.0
        print("RESULT:", "OK — CU read $340 detention" if ok else "UNEXPECTED fields")
        return 0 if ok else 1
    finally:
        cu.close()


if __name__ == "__main__":
    sys.exit(main())
