"""Real Gemini Computer Use worker (model gemini-2.5-computer-use-preview-10-2025).

Implements the `ComputerUse` protocol by driving a headful Playwright browser
with the Gemini Computer Use agentic loop: the model sees a screenshot and emits
UI actions (legacy vocabulary), we execute them and send back a fresh screenshot,
until it stops. The model does the *operating*; we read the resulting rendered
DOM (via [data-field] hooks) for deterministic Observation.fields.

Playwright sync objects are thread-bound, so the browser lives on one dedicated
worker thread; `run()` submits a task and blocks for the result. This keeps the
orchestrator's synchronous `computer_use.run(task)` contract unchanged.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from concurrent.futures import Future
from datetime import datetime, timezone

from google import genai
from google.genai import types

from ..audit.artifacts import save_bytes
from ..board.models import ActionResult, Observation, System, Task, TaskKind
from .browser import BrowserComputer

logger = logging.getLogger("computer_use.gemini")

CU_MODEL = os.environ.get("CU_MODEL", "gemini-2.5-computer-use-preview-10-2025")
PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
MAX_TURNS = int(os.environ.get("CU_MAX_TURNS", "8"))

# System -> portal page (each portal is a Vite page; CU navigates by URL).
PORTAL_PAGE = {
    System.tms: "tms.html",
    System.customs: "index.html",
    System.carrier: "carrier.html",
    System.terminal: "terminal.html",
}

PREAMBLE = (
    "You operate a logistics web portal for a freight forwarder, like a human "
    "employee. Do exactly what the task says using on-screen controls, then stop. "
    "Be concise and do not navigate away from the current page.\n\nTASK: "
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def denorm(value, size: int) -> int:
    """Model coordinates are normalized to 0–1000; scale to actual pixels."""
    return int(float(value) / 1000 * size)


def _goal(task: Task) -> str:
    ref = task.params.get("reference") or ""
    s = task.target_system
    if task.kind == TaskKind.act and s == System.terminal:
        return (f"A detention charge with reference {ref} must be settled. Type "
                f"'{ref}' into the reference lookup field, click 'Look up', then "
                f"click the 'Pay & release' button to settle and release it.")
    if s == System.terminal and ref:
        return (f"Type the gate reference '{ref}' into the reference lookup field "
                f"and click 'Look up' to display any charge for it.")
    if s == System.terminal:
        return ("Look at the terminal gate portal. Do NOT enter any reference. "
                "Report whether any charge is currently displayed.")
    if s == System.carrier:
        return "Read the carrier portal. Report container MSKU4471's status and whether it has a hold."
    if s == System.customs:
        return "Read the ICS2 customs decision register. Report MSKU4471's customs decision."
    return "Read this portal and report the status shown for container MSKU4471."


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tools=[types.Tool(computer_use=types.ComputerUse(
            environment=types.Environment.ENVIRONMENT_BROWSER))],
    )


class RealComputerUse:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._err: Exception | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=60)
        if self._err:
            raise self._err

    # ---- public contract (called from any thread) --------------------------
    def run(self, task: Task) -> Observation | ActionResult:
        fut: Future = Future()
        self._q.put((task, fut))
        return fut.result()

    def close(self) -> None:
        self._q.put((None, None))

    # ---- dedicated worker thread ------------------------------------------
    def _serve(self) -> None:
        try:
            self._browser = BrowserComputer()
            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        except Exception as e:  # surface init failure to constructor
            self._err = e
            self._ready.set()
            return
        self._ready.set()
        while True:
            task, fut = self._q.get()
            if task is None:
                self._browser.close()
                return
            try:
                fut.set_result(self._handle(task))
            except Exception as e:  # noqa: BLE001 — report to caller
                logger.exception("CU task failed: %s", task.goal)
                fut.set_exception(e)

    def _ensure_browser(self) -> None:
        """Relaunch if the headful window/context was closed (manually, crash, or
        a stale profile lock) — otherwise every later task cascades on a dead page."""
        if self._browser is not None and self._browser.is_alive():
            return
        logger.warning("CU browser not alive — relaunching")
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        self._browser = BrowserComputer()

    def _handle(self, task: Task) -> Observation | ActionResult:
        self._ensure_browser()
        b = self._browser
        b.navigate(f"{PORTAL_BASE_URL}/{PORTAL_PAGE[task.target_system]}")
        self._settle()
        cid = task.params.get("container_id", "")

        if task.kind == TaskKind.read:
            self._cu_loop(_goal(task), allow_financial=False)
            fields = self._extract(task.target_system, cid)
            return Observation(
                container_id=cid, source_system=task.target_system, fields=fields,
                screenshot_path=save_bytes(f"read_{task.target_system.value}_{cid}", b.screenshot()),
                confidence=1.0, ts=_now(),
            )

        before = save_bytes(f"act_before_{task.target_system.value}_{cid}", b.screenshot())
        self._cu_loop(_goal(task), allow_financial=True)
        after = save_bytes(f"act_after_{task.target_system.value}_{cid}", b.screenshot())
        fields = self._extract(task.target_system, cid)  # verify re-read
        verified = fields.get("detention_unpaid") is False or fields.get("paid") is True
        return ActionResult(ok=True, target_system=task.target_system, before_shot=before,
                            after_shot=after, verified=verified, ts=_now())

    # ---- the agentic loop --------------------------------------------------
    def _cu_loop(self, goal: str, allow_financial: bool) -> None:
        b = self._browser
        contents = [types.Content(role="user", parts=[
            types.Part(text=PREAMBLE + goal),
            types.Part.from_bytes(data=b.screenshot(), mime_type="image/png"),
        ])]
        for _ in range(MAX_TURNS):
            resp = self._client.models.generate_content(
                model=CU_MODEL, contents=contents, config=_config())
            cand = resp.candidates[0]
            contents.append(cand.content)
            calls = [p.function_call for p in (cand.content.parts or []) if p.function_call]
            if not calls:
                return
            responses = []
            for fc in calls:
                extra = self._dispatch(fc, allow_financial)
                responses.append(types.FunctionResponse(
                    name=fc.name,
                    response={"url": b.current_url(), **extra},
                    parts=[types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(
                        mime_type="image/png", data=b.screenshot()))],
                ))
            contents.append(types.Content(role="user", parts=[
                types.Part(function_response=fr) for fr in responses]))

    def _dispatch(self, fc, allow_financial: bool) -> dict:
        b = self._browser
        w, h = b.screen_size()
        args = dict(fc.args or {})

        # financial/other confirmation: the orchestrator already enforced the human
        # /approve before dispatching an act, so the act path auto-acknowledges.
        extra: dict = {}
        safety = args.get("safety_decision")
        if safety and safety.get("decision") == "require_confirmation":
            if not allow_financial:
                logger.warning("read hit a confirmation gate — stopping: %s", safety)
                return {"safety_acknowledgement": "false"}
            extra["safety_acknowledgement"] = "true"

        def dx(v): return denorm(v, w)
        def dy(v): return denorm(v, h)

        name = fc.name
        if name == "navigate":
            b.navigate(args["url"]); self._settle()
        elif name == "click_at":
            b.click_at(dx(args["x"]), dy(args["y"]))
        elif name == "hover_at":
            b.hover_at(dx(args["x"]), dy(args["y"]))
        elif name == "type_text_at":
            b.type_text_at(dx(args["x"]), dy(args["y"]), args.get("text", ""),
                           bool(args.get("press_enter", False)),
                           bool(args.get("clear_before_typing", True)))
        elif name == "scroll_document":
            b.scroll_document(args.get("direction", "down"))
        elif name == "scroll_at":
            mag = int(args.get("magnitude", 800))
            b.scroll_at(dx(args["x"]), dy(args["y"]), args.get("direction", "down"), mag)
        elif name == "key_combination":
            b.key_combination(args.get("keys", ""))
        elif name == "drag_and_drop":
            b.drag_and_drop(dx(args["x"]), dy(args["y"]),
                            dx(args["destination_x"]), dy(args["destination_y"]))
        elif name == "go_back":
            b.go_back()
        elif name == "go_forward":
            b.go_forward()
        elif name in ("wait_5_seconds", "wait"):
            b.wait_5_seconds()
        elif name == "open_web_browser":
            b.open_web_browser()
        else:
            logger.warning("unhandled CU action: %s", name)
        b.page.wait_for_timeout(250)
        return extra

    # ---- DOM extraction ----------------------------------------------------
    def _settle(self) -> None:
        try:
            self._browser.page.wait_for_selector("[data-field]", timeout=4000)
        except Exception:  # noqa: BLE001
            self._browser.page.wait_for_timeout(500)

    def _extract(self, system: System, container_id: str) -> dict:
        rows = self._browser.collect_data_fields()

        if system == System.terminal:
            panel = next((r for r in rows if r["field"] == "charge_panel"), None)
            if not panel:
                return {}
            d = panel["dataset"]
            return {
                "detention_unpaid": d.get("detentionUnpaid") == "true",
                "amount_usd": float(d.get("amountUsd", 0) or 0),
                "reference": d.get("reference"),
                "paid": d.get("paid") == "true",
            }
        if system == System.carrier:
            row = next((r for r in rows if r["field"] == "carrier_row"
                        and r["dataset"].get("container") == container_id), None)
            if not row:
                return {}
            return {"status": row["dataset"].get("status"),
                    "hold": row["dataset"].get("hold") == "true"}
        if system == System.customs:
            row = next((r for r in rows if r["field"] == "customs_row"
                        and r["dataset"].get("container") == container_id), None)
            if not row:
                return {}
            return {"status": row["dataset"].get("status"),
                    "reason": row["dataset"].get("reason") or None}
        return {}  # tms and anything else read clean
