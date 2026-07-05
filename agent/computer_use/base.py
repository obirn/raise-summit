"""Computer Use contract (MASTER_PROMPT §3/§8).

`run(task) -> Observation | ActionResult`. The orchestrator depends only on this
interface, so the M1 stub and the M2 real Gemini-CU-+-Playwright worker are
interchangeable. Reads are auto; acts are only ever dispatched after a human
/approve (gate policy lives in the orchestrator, not here).
"""

from __future__ import annotations

from typing import Protocol

from ..board.models import ActionResult, Observation, Task


class ComputerUse(Protocol):
    def run(self, task: Task) -> Observation | ActionResult: ...
