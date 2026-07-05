"""Solver-agent brains — the *planner* tier.

A brain decides the NEXT tool call given the container's held state + the steps
so far. It never touches portals directly: the tools it emits are executed by the
SolverAgent against the engine's tool-primitives (which use Computer Use). Two
brains are interchangeable behind the `Brain` protocol:
- `ScriptedBrain`  — deterministic FSM, offline (tests + demo-safe fallback).
- `GeminiFunctionCallingBrain` — real Gemini function-calling (manual loop),
  reconstructed from the persisted step history each call, so it is resumable.

The planner is a normal text model (AGENT_MODEL); the *clicking* is done by the
separate Computer Use worker — this two-tier split keeps our headful local
browser (invariant 1) and avoids the "computer_use must be the sole tool" limit.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("solver.brain")

AGENT_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")
ANTIGRAVITY_AGENT = os.environ.get("ANTIGRAVITY_AGENT", "antigravity-preview-05-2026")

_JSON_TYPE = {"STRING": "string", "NUMBER": "number", "INTEGER": "integer",
              "BOOLEAN": "boolean", "OBJECT": "object", "ARRAY": "array"}

# Portal read order when nothing more specific is known.
_DEFAULT_ORDER = ["terminal", "tms", "carrier", "customs"]


@dataclass
class BrainContext:
    container_id: str
    goal: str
    phase: str                 # "plan" | "execute"
    held_state: dict           # id/status/blockers/dollars_at_risk/hint_system/known_reference
    steps: list[dict]          # [{tool, args, result}] so far (persisted -> resumable)
    # Antigravity/Interactions durable-reasoning handles (M6; other brains ignore)
    previous_interaction_id: str | None = None
    environment_id: str | None = None
    pending_call_id: str | None = None


@dataclass
class ToolCall:
    name: str
    args: dict
    # Interaction handles the AntigravityBrain returns for the agent to persist
    interaction_id: str | None = None
    environment_id: str | None = None
    call_id: str | None = None


class Brain(Protocol):
    def next_action(self, ctx: BrainContext) -> ToolCall: ...


# ---- tool schema (shared; Gemini FunctionDeclarations built from this) ------
TOOL_SPECS = [
    {
        "name": "read_portal",
        "description": "Open a portal via Computer Use and read the status shown for this "
                       "container. Returns parsed fields and any binding blocker found.",
        "params": {
            "system": ("STRING", "Which portal: tms | carrier | customs | terminal"),
            "reference": ("STRING", "Gate reference for the terminal portal, if known (else omit)"),
        },
        "required": ["system"],
    },
    {
        "name": "surface_blocker",
        "description": "Surface the single binding blocker to the human coordinator for one-tap "
                       "approval. Use ONLY for the real cause. Does NOT pay — a human must approve.",
        "params": {
            "blocker_type": ("STRING", "e.g. unpaid_detention | customs_hold | carrier_hold"),
            "source_system": ("STRING", "portal where the blocker lives"),
            "evidence": ("STRING", "short human-readable evidence, e.g. 'unpaid terminal detention $340'"),
            "reference": ("STRING", "gate reference if any"),
        },
        "required": ["blocker_type", "source_system", "evidence"],
    },
    {
        "name": "mark_unlocatable",
        "description": "Call when every accessible portal reads clean — the cause is on no "
                       "system you can see (it will arrive via a driver voice call).",
        "params": {"reason": ("STRING", "why nothing was found")},
        "required": [],
    },
    {
        "name": "execute_approved_action",
        "description": "Run the approved fix via Computer Use, then verify. Only available after "
                       "a human approved the surfaced action.",
        "params": {},
        "required": [],
    },
    {
        "name": "done",
        "description": "Finish: nothing left to do for this container.",
        "params": {"summary": ("STRING", "one line")},
        "required": [],
    },
]

TERMINAL_TOOLS = {"surface_blocker", "mark_unlocatable", "execute_approved_action", "done"}


# ---- deterministic FSM brain (offline) -------------------------------------
class ScriptedBrain:
    """Reproduces the deterministic diagnose logic as an agent plan: read the
    likely system first, then the rest; surface the first blocker found; if all
    clean, mark unlocatable. In execute phase: run the approved action, then done."""

    def next_action(self, ctx: BrainContext) -> ToolCall:
        if ctx.phase == "execute":
            if not any(s["tool"] == "execute_approved_action" for s in ctx.steps):
                return ToolCall("execute_approved_action", {})
            return ToolCall("done", {"summary": "resolved"})

        reads = [s for s in ctx.steps if s["tool"] == "read_portal"]
        # surface the first blocker any read revealed
        for s in reads:
            blk = (s.get("result") or {}).get("blocker")
            if blk:
                return ToolCall("surface_blocker", {
                    "blocker_type": blk["type"], "source_system": blk["source_system"],
                    "evidence": blk["evidence"], "reference": blk.get("reference") or "",
                })
        # otherwise read the next unread system (likely one first)
        read_systems = {(s.get("args") or {}).get("system") for s in reads}
        order: list[str] = []
        hint = ctx.held_state.get("hint_system")
        if hint:
            order.append(hint)
        order += [s for s in _DEFAULT_ORDER if s not in order]
        for system in order:
            if system not in read_systems:
                args = {"system": system}
                if system == "terminal" and ctx.held_state.get("known_reference"):
                    args["reference"] = ctx.held_state["known_reference"]
                return ToolCall("read_portal", args)
        # everything read, nothing binding
        return ToolCall("mark_unlocatable", {"reason": "all accessible portals clean"})


# ---- real Gemini function-calling brain ------------------------------------
class GeminiFunctionCallingBrain:
    """Manual function-calling loop, re-driven from the persisted step history on
    every call (so a resumed agent reconstructs its plan). Returns exactly one
    next ToolCall; the SolverAgent executes it and appends the result."""

    def __init__(self) -> None:
        self._client = None  # lazy: import without GEMINI_API_KEY

    def _client_or_init(self):
        if self._client is None:
            from dotenv import load_dotenv
            from google import genai
            load_dotenv()
            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return self._client

    def _tools(self):
        from google.genai import types
        decls = []
        for spec in TOOL_SPECS:
            props = {
                name: types.Schema(type=getattr(types.Type, t), description=d)
                for name, (t, d) in spec["params"].items()
            }
            decls.append(types.FunctionDeclaration(
                name=spec["name"], description=spec["description"],
                parameters=types.Schema(type=types.Type.OBJECT, properties=props,
                                        required=spec["required"]) if props else None,
            ))
        return [types.Tool(function_declarations=decls)]

    def _system_instruction(self, ctx: BrainContext) -> str:
        return (
            "You are a solver agent for a freight forwarder, unblocking one stuck "
            "container by operating closed web portals through their UI. Rules:\n"
            "- To learn a portal's status you MUST call read_portal (you cannot see a portal "
            "without reading it). Read the most likely system first.\n"
            "- Surface exactly ONE binding blocker (the real cause) with surface_blocker; a human "
            "approves before anything is paid. NEVER attempt to pay or release yourself.\n"
            "- If every accessible portal reads clean, call mark_unlocatable (the cause will come "
            "from a driver phone call).\n"
            "- The terminal portal shows nothing unless you pass the exact gate reference.\n"
            f"Goal: {ctx.goal}"
        )

    def next_action(self, ctx: BrainContext) -> ToolCall:
        from google.genai import types
        client = self._client_or_init()

        contents = [types.Content(role="user", parts=[types.Part(
            text="Container held state (no portal has been read yet unless shown in history):\n"
                 + json.dumps(ctx.held_state, default=str)
                 + f"\nPhase: {ctx.phase}. Decide the next single tool call.")])]
        # replay history as function_call / function_response pairs
        for s in ctx.steps:
            contents.append(types.Content(role="model", parts=[types.Part(
                function_call=types.FunctionCall(name=s["tool"], args=s.get("args") or {}))]))
            contents.append(types.Content(role="user", parts=[types.Part(
                function_response=types.FunctionResponse(
                    name=s["tool"], response={"result": s.get("result")}))]))

        resp = client.models.generate_content(
            model=AGENT_MODEL, contents=contents,
            config=types.GenerateContentConfig(
                tools=self._tools(),
                system_instruction=self._system_instruction(ctx),
                temperature=0,
            ),
        )
        parts = resp.candidates[0].content.parts or []
        for p in parts:
            if p.function_call:
                return ToolCall(p.function_call.name, dict(p.function_call.args or {}))
        # no function call -> the model thinks it's done
        text = " ".join(p.text for p in parts if p.text)
        logger.info("brain returned no tool call, treating as done: %s", text[:120])
        return ToolCall("done", {"summary": text[:120] or "no action"})


# ---- Antigravity Interactions API brain (durable reasoning, M6) ------------
def _s(obj, key, default=None):
    """Read a field from a step/interaction that may be a pydantic model or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _function_tools() -> list[dict]:
    """Our tool surface as Interactions API `function` tool declarations."""
    tools = []
    for spec in TOOL_SPECS:
        props = {n: {"type": _JSON_TYPE.get(t, "string"), "description": d}
                 for n, (t, d) in spec["params"].items()}
        tools.append({
            "type": "function", "name": spec["name"], "description": spec["description"],
            "parameters": {"type": "object", "properties": props, "required": spec["required"]},
        })
    return tools


_ANTIGRAVITY_INSTRUCTION = (
    "You are a solver agent unblocking one stuck freight container by operating closed web "
    "portals. Emit exactly ONE function call for the next action. You cannot see a portal "
    "without calling read_portal. Surface exactly one binding blocker (surface_blocker); a human "
    "approves before anything is paid — never pay yourself. If every accessible portal reads "
    "clean, call mark_unlocatable. The terminal portal shows nothing without the exact reference."
)


class AntigravityBrain:
    """Planner tier seated in a durable Gemini Interaction (`antigravity-preview-05-2026`).

    The agent's reasoning lives SERVER-SIDE: each decision is a `function_call` handed back at
    `status=="requires_action"`; we execute it locally and continue via `previous_interaction_id`
    (no history resend — the server keeps context). The board persists only the interaction
    handles, so a resumed process continues the SAME reasoning by id — this is the load-bearing
    durability. On any API error/timeout it falls back to the local Gemini brain so the demo never
    stalls. Inject `client` (with `.interactions.create/.get`) for offline tests.
    """

    def __init__(self, client=None, variant: str | None = None, poll_interval: float = 3.0,
                 max_wait: float | None = None, sleep=time.sleep) -> None:
        self._client = client
        self.variant = variant or os.environ.get("ANTIGRAVITY_VARIANT", "agent")  # agent | model
        self.background = self.variant == "agent"
        self.poll_interval = poll_interval
        self.max_wait = max_wait if max_wait is not None else float(os.environ.get("ANTIGRAVITY_MAX_WAIT", "90"))
        self._sleep = sleep
        self._fallback_brain: Brain | None = None

    def _client_or_init(self):
        if self._client is None:
            from dotenv import load_dotenv
            from google import genai
            load_dotenv()
            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return self._client

    def _fallback(self) -> Brain:
        if self._fallback_brain is None:
            self._fallback_brain = GeminiFunctionCallingBrain()
        return self._fallback_brain

    def next_action(self, ctx: BrainContext) -> ToolCall:
        try:
            return self._decide(ctx)
        except Exception as e:  # noqa: BLE001 — resilience: never stall the demo
            logger.warning("AntigravityBrain fell back to Gemini brain: %s", e)
            return self._fallback().next_action(ctx)

    def _decide(self, ctx: BrainContext) -> ToolCall:
        client = self._client_or_init()
        ix = self._poll(client, self._create_or_continue(client, ctx))
        status = _s(ix, "status")
        iid, env_id = _s(ix, "id"), (_s(ix, "environment_id") or ctx.environment_id)

        if status == "requires_action":
            fc = next((s for s in (_s(ix, "steps") or []) if _s(s, "type") == "function_call"), None)
            if fc is None:
                raise RuntimeError("requires_action without a function_call step")
            return ToolCall(_s(fc, "name"), dict(_s(fc, "arguments") or {}),
                            interaction_id=iid, environment_id=env_id, call_id=_s(fc, "id"))
        if status == "completed":
            return ToolCall("done", {"summary": (_s(ix, "output_text") or "")[:200]},
                            interaction_id=iid, environment_id=env_id)
        raise RuntimeError(f"interaction ended status={status}")

    def _create_or_continue(self, client, ctx: BrainContext):
        tools = _function_tools()
        if not ctx.previous_interaction_id:
            prompt = (f"{_ANTIGRAVITY_INSTRUCTION}\nGoal: {ctx.goal}\nContainer held state:\n"
                      + json.dumps(ctx.held_state, default=str))
            return self._create(client, input=prompt, tools=tools, fresh=True)
        # continue: feed the just-executed tool's result back as a function_result
        last = ctx.steps[-1] if ctx.steps else {}
        result_step = [{"type": "function_result", "call_id": ctx.pending_call_id or "",
                        "result": last.get("result", {})}]
        return self._create(client, input=result_step, tools=tools, fresh=False,
                            previous_interaction_id=ctx.previous_interaction_id,
                            environment=ctx.environment_id)

    def _create(self, client, *, input, tools, fresh, previous_interaction_id=None, environment=None):
        kwargs = dict(input=input, tools=tools, store=True, background=self.background)
        if self.variant == "model":
            kwargs["model"] = AGENT_MODEL
        else:
            kwargs["agent"] = ANTIGRAVITY_AGENT
            kwargs["environment"] = {"type": "remote"} if fresh else (environment or {"type": "remote"})
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id
        return client.interactions.create(**kwargs)

    def _poll(self, client, ix):
        waited = 0.0
        while _s(ix, "status") == "in_progress":
            if waited >= self.max_wait:
                raise TimeoutError("interaction poll timed out")
            self._sleep(self.poll_interval)
            waited += self.poll_interval
            ix = client.interactions.get(id=_s(ix, "id"))
        return ix


def make_brain(kind: str) -> Brain:
    if kind == "gemini":
        return GeminiFunctionCallingBrain()
    if kind == "antigravity":
        return AntigravityBrain()
    return ScriptedBrain()
