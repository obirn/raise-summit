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
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("solver.brain")

AGENT_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

# Portal read order when nothing more specific is known.
_DEFAULT_ORDER = ["terminal", "tms", "carrier", "customs"]


@dataclass
class BrainContext:
    container_id: str
    goal: str
    phase: str                 # "plan" | "execute"
    held_state: dict           # id/status/blockers/dollars_at_risk/hint_system/known_reference
    steps: list[dict]          # [{tool, args, result}] so far (persisted -> resumable)


@dataclass
class ToolCall:
    name: str
    args: dict


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


def make_brain(kind: str) -> Brain:
    if kind == "gemini":
        return GeminiFunctionCallingBrain()
    return ScriptedBrain()
