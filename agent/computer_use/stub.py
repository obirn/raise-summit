"""DEMO-ONLY Computer Use stub (M1).

Stands in for the browser that the real M2 worker will drive with Gemini
Computer Use + Playwright. The `_TRUTH` dict below is the stand-in for what CU
would *see on screen* — i.e. the portals' localStorage — NOT a portal backend
the agent calls. In M2 this dict disappears: reads come from real screenshots
and acts click real buttons. Crucially it already enforces invariant 6: the
terminal detention is invisible unless the read passes the driver's reference.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..audit.artifacts import save_screenshot
from ..board.models import ActionResult, Observation, System, Task, TaskKind
from seed.scenario import TERMINAL_DETENTION_USD, TERMINAL_REFERENCE


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StubComputerUse:
    def __init__(self) -> None:
        # Mutable "on screen" truth. Acts mutate it; re-reads verify.
        self._truth: dict[str, dict] = {
            "MSKU4471": {
                "tms": {"status": "ready to pickup"},
                "carrier": {"status": "available", "hold": False},
                "customs": {"status": "released"},
                # invisible until queried with the exact reference:
                "terminal": {
                    "reference": TERMINAL_REFERENCE,
                    "detention_usd": TERMINAL_DETENTION_USD,
                    "paid": False,
                },
            },
            "TCLU3380": {
                "tms": {"status": "ready to pickup"},
                "carrier": {"status": "available", "hold": False},
                # screen-only blocker — no voice needed:
                "customs": {"status": "hold", "reason": "HS code invalid"},
                "terminal": {"reference": None},
            },
        }

    # ---- reads -------------------------------------------------------------
    def _read_fields(self, task: Task) -> dict:
        truth = self._truth.get(task.params.get("container_id", ""), {})
        sys = task.target_system

        if sys == System.terminal:
            t = truth.get("terminal", {})
            ref = task.params.get("reference")
            # invariant 6: nothing without the exact driver reference
            if not ref or ref != t.get("reference"):
                return {}
            if t.get("paid"):
                return {"detention_unpaid": False, "reference": ref, "amount_usd": 0.0}
            return {
                "detention_unpaid": True,
                "amount_usd": t.get("detention_usd", 0.0),
                "reference": ref,
            }

        return dict(truth.get(sys.value, {}))

    # ---- act ---------------------------------------------------------------
    def _apply_act(self, task: Task) -> bool:
        """Pay/release the terminal detention (the only high action in demo)."""
        cid = task.params.get("container_id", "")
        if task.target_system == System.terminal and cid in self._truth:
            self._truth[cid]["terminal"]["paid"] = True
            return True
        return False

    # ---- contract ----------------------------------------------------------
    def run(self, task: Task) -> Observation | ActionResult:
        cid = task.params.get("container_id", "")
        if task.kind == TaskKind.read:
            fields = self._read_fields(task)
            return Observation(
                container_id=cid,
                source_system=task.target_system,
                fields=fields,
                screenshot_path=save_screenshot(f"read_{task.target_system.value}_{cid}"),
                confidence=1.0,
                ts=_now(),
            )

        before = save_screenshot(f"act_before_{task.target_system.value}_{cid}")
        ok = self._apply_act(task)
        after = save_screenshot(f"act_after_{task.target_system.value}_{cid}")
        # ALWAYS re-read to confirm the change (§8).
        verified = ok and not self._read_fields(
            Task(kind=TaskKind.read, target_system=task.target_system, goal="verify",
                 params={**task.params})
        ).get("detention_unpaid", True)
        return ActionResult(
            ok=ok,
            target_system=task.target_system,
            before_shot=before,
            after_shot=after,
            verified=verified,
            ts=_now(),
        )
