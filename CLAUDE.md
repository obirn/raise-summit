# CLAUDE.md — Unblock

Standing conventions and hard rules for this repo. **Read this before writing any code**, and keep it updated as the single source of truth for how the project works. If you take a shortcut that contradicts a rule here, either don't — or update this file and flag it as `DEMO-ONLY`.

---

## What this is

**Unblock** — an agent that resolves *stuck-container exceptions* for a mid-size freight forwarder by operating closed, no-API systems the way a human does, and holding a durable exception state across a long horizon.

Hackathon deliverable for **Google DeepMind (in-person)**. Three primitives, each load-bearing:
- **Gemini Computer Use** — sees a screen, clicks. The *only* way into systems with no API.
- **Antigravity** — persistent state on a long task; resume-by-ID between sessions.
- **Live Translate** — two-way field voice, across languages, mid-conversation.

This repo is a **DEMO with fake portals**. It is not production. Every place a real-world concern is stubbed (MFA, telephony, ToS, credentials) is marked `DEMO-ONLY`.

---

## The seven invariants — never violate

1. **No backdoor.** The agent reaches every portal **only through its UI, via Computer Use, using the forwarder's own credentials** — never by calling the portal's internal API/DB. The fake portals *have* backends; the agent code **must not** import, call, or query them directly. If a container's status changes, it changes because CU clicked, not because the orchestrator wrote to the portal's store. Breaking this deletes the entire reason the project exists.
2. **Time triggers vision, never the reverse.** Detection is deterministic math on held state + the free-time clock. Computer Use is invoked **only** when the alert engine decides a read is worth its cost. No polling portals in a loop.
3. **Human gate on high-cost/irreversible actions** (pay, file, submit). Always surface **one** plain-language line + a one-tap approve/dismiss **before** CU executes. Reads are auto; writes are gated.
4. **The board is the single source of truth.** All state persists to SQLite. `resume(env_id)` re-hydrates board + knowledge base from disk — no state lives only in memory. Killing the process mid-run and restarting must lose nothing.
5. **Audit trail is first-class.** Every observation and every action is logged with a screenshot artifact and a timestamp. This doubles as **demurrage-dispute evidence** — treat it as a product feature, not a debug log.
6. **Live Translate is load-bearing only at the terminal/no-feed blocker.** The terminal detention is discoverable **only** via the driver-provided reference code. The agent must be *structurally unable* to find it without the call. Do not let any monitored portal expose it.
7. **Agent scope = forwarder scope.** The agent has exactly the access a forwarder employee has, no more. It never claims access to systems the forwarder has no login for (terminal internal ops, customs internal review). It sees their *effects* (a hold notice, a gate refusal), not their internals.

---

## Actual architecture (reconciliation — READ THIS)

The aspirational "Stack"/"Repo layout" below described `/portals/*` React apps with
per-portal mock backends. The real repo diverged; here is ground truth as built:

- **Portals are pages of one Vite app, not `/portals/*` services.** A single Vite 8 +
  React 19 + Tailwind app with one HTML entry per portal: `index.html` (Customs ICS2),
  `tms.html` (TMS, also wrapped by Electron), plus `carrier.html` / `terminal.html` to
  build in M2, and `ui.html` (the coordinator "site office", built). CU navigates by URL.
- **No mock backends. Portal state is client-only (localStorage + React).** This is how
  **invariant 1** is realized: the Python agent has *no* path to portal state except the
  browser UI via Computer Use + Playwright — structurally, not by discipline. The SQLite
  **board is the agent's own exception state**, separate from portal state.
- **Carrier did not pre-exist; TMS is an Electron desktop app** (not a plain web portal).
- **Python is 3.12** (the `.venv`), not 3.11. **Node ≥20 is required** by Vite 8; this repo
  uses Node 22 via `nvm` (system node may be older — `scripts/env.sh` loads it).
- **Voice** lives on the `twilio` branch as real source (`twilio_gemini_bridge.py` +
  `tools/gate.py`, Gemini Live model `gemini-3.1-flash-live-preview`); integrate in M3.
- **Ports (final):** orchestrator `5000` (REST+WS+`/artifacts`), Vite `5173` (all portal
  pages + UI), voice bridge `8080` (M3). The `4001–4004` table below is nominal only.

**Confirmed Computer Use API (verified vs live docs + installed SDK — do not re-guess):**
- Model **`gemini-2.5-computer-use-preview-10-2025`**; `google-genai` **2.10** already supports it
  (no upgrade). Uses the **legacy** action vocabulary for this model.
- Tool: `types.Tool(computer_use=types.ComputerUse(environment=types.Environment.ENVIRONMENT_BROWSER))`.
- Loop: `client.models.generate_content(model, contents, config)` → read `part.function_call` →
  execute via Playwright → reply `Content(role="user", parts=[Part(function_response=FunctionResponse(
  name, response={"url":url}, parts=[FunctionResponsePart(inline_data=FunctionResponseBlob(
  mime_type="image/png", data=<raw PNG bytes>))]))])` → repeat until no calls.
- Actions: `open_web_browser, navigate, click_at, hover_at, type_text_at, scroll_document,
  scroll_at, key_combination, drag_and_drop, go_back/forward, wait_5_seconds`. Coords are
  **normalized 0–1000** → scale to viewport pixels. `safety_decision=require_confirmation`
  (e.g. `FINANCIAL_TRANSACTIONS` on pay) → add `"safety_acknowledgement":"true"`; our act path
  auto-acks because the orchestrator already enforced the human `/approve`. Impl:
  [agent/computer_use/gemini_cu.py](agent/computer_use/gemini_cu.py) + [browser.py](agent/computer_use/browser.py).

**M1 status (built + tested):** board (SQLite, lossless `resume`), monitoring (`tick`),
orchestrator state machine + gate policy + FastAPI REST/WS, voice **stub**, seed, coordinator UI.

**M2 status (built + tested):** real Gemini Computer Use + Playwright (headful, persistent
profile) behind the `ComputerUse` protocol; carrier + terminal portal pages (+ customs decision
register), each with `data-field` hooks for deterministic DOM extraction; `CU_MODE=stub|real`
switch in the orchestrator (`_make_cu`, falls back to stub on failure). Verified live: the CU
model drove the browser through the **full golden path** (reads all 4 portals → `stalled_unlocatable`
→ voice ref → targeted terminal read reveals **$340** → human approve → CU clicks **Pay & release**,
`verified=True` → `resolving`) with real screenshots in the audit trail; the terminal stays blank
without the reference (invariant 6). `make demo` (stub) / `make demo-cu` (real CU) / `make cu-smoke`
(one live CU read). `make golden` + `make test` (**9/9**) stay on the stub — deterministic, offline.

**M3 status (built + tested):** real **Live Translate** — the phone-tested Twilio↔Gemini-Live
bridge relocated to [agent/voice/twilio_bridge.py](agent/voice/twilio_bridge.py) + [gate.py](agent/voice/gate.py)
(Gemini Live `gemini-3.1-flash-live-preview`, lazy client). It's a *push* path: on the driver's
`flag_blocked_at_gate` tool-call it POSTs `/events/field-truth` to the orchestrator, which runs the
same flow as the scripted demo (targeted terminal read → surfaced line → human gate); it also POSTs
`/events/call-started` + `/events/transcript` (live ES↔EN in the Site Office). `engine.on_call`
(pull/`StubVoice`, offline default) and `ingest_field_truth` (push) converge on one method. Run:
`make voice` (`:8080`) + ngrok + Twilio webhook (`DEMO-ONLY`). Verified: live push path
`field-truth → resolving`; `make test` **12/12** stays offline on the stub.

**M5 status (built + tested):** agentic layer. `AGENT_MODE=agentic` makes the orchestrator
**spawn one durable solver agent per stuck container** ([agent/solver/](agent/solver/)); each
reasons with Gemini **function calling** (`agent/solver/brain.py`, `AGENT_MODEL`) to plan which
portals to read/act, calls the engine tool-primitives (`tool_read_portal` / `tool_surface_blocker`
/ `tool_mark_unlocatable` / `tool_execute_approved_action`) which reuse the **same** transitions
(so all 7 invariants hold: CU-only reads, human gate, audit, resumable board). State persists on
`Container.agent` (AgentState) → **resumable by agent_id** (the "Antigravity" capability). Two-tier:
the planner decides, the **Computer Use worker clicks** (keeps our headful local browser + inv 1).
`ScriptedBrain` keeps it offline (15/15 tests); the real Gemini brain surfaced $340 live. The
deterministic state machine remains the `AGENT_MODE=deterministic` default. Run: `make agentic`.

**Antigravity note:** the *product* is an agentic IDE with **no backend SDK** — not embeddable.
But `google-genai` 2.10's experimental `client.interactions.create(agent="antigravity-preview-05-2026",
environment={"type":"remote"}, store, background, previous_interaction_id)` **is reachable with our
key** (`make antigravity-probe` created an interaction). Its agent runs in a remote sandbox, so
using it to drive our localhost portals needs a public URL — a documented follow-up, not the
current path (our own solver agents + local CU are the working implementation).

**M6 status (built + tested):** the Antigravity **Interactions API is now the load-bearing durable
brain** (`AGENT_BRAIN=antigravity`). `AntigravityBrain` ([agent/solver/brain.py](agent/solver/brain.py))
seats the solver agent's *reasoning* inside a durable interaction (`antigravity-preview-05-2026`):
each decision is a `function_call` handed back at `requires_action`, **our local CU executes it**,
and we continue via `previous_interaction_id` (server keeps context — no history resent). The board
persists only the handles (`AgentState.{previous_interaction_id,environment_id,pending_call_id}`), so
killing the process and resuming continues the **same server-side interaction by id** — remove
Antigravity and the agent can't resume its reasoning (that's what makes it load-bearing, not a
bolt-on). Two-tier still holds: Antigravity plans, our Computer Use clicks (invariant 1). Falls back
to the local Gemini brain on any API error (demo never stalls); `ANTIGRAVITY_VARIANT=agent|model`
lever. Verified live (real handoff `read_portal(DET-4471-B)`) + offline resume-by-id (`FakeInteractions`);
`make test` **17/17**. Run: `make agentic AGENT_BRAIN=antigravity` (`CU_MODE=real` for real clicks).

**M4 (next):** audit polish, MASTER_PROMPT.md, hardening; optional real `voice.callback`.

---

## Stack

> Match the stack of the **existing TMS mirror and carrier portal** already in this repo. The defaults below assume the common case — adapt if the mirrors differ, and record the final choice here. **See "Actual architecture" above for what was actually built** where this diverges.

- **Fake portals** (TMS, carrier, customs, terminal): React + Vite, served as pages of one Vite app. State is **client-only (localStorage)** — there is NO per-portal backend (that is deliberate: it makes Computer Use the only way in — invariant 1). TMS + Customs exist; carrier + terminal are built in M2.
- **Orchestrator / agent** (control plane): Python 3.12, FastAPI service. Owns the state machine, the alert engine, the board, and the calls to Gemini.
- **Computer Use worker**: Gemini Computer Use (model `gemini-2.5-computer-use-preview-10-2025`) via `client.models.generate_content` with the `computer_use` tool, executing UI actions against the portals through **Playwright** (headful so the audience sees the clicks). Exact signatures confirmed above — built in M2. (Not the Interactions API.)
- **Live Translate**: Gemini Live / Live Translate streaming API for two-way voice. `DEMO-ONLY` fallback: a pre-recorded Spanish driver track + scripted transcript, triggerable if live audio fails.
- **State**: SQLite via SQLModel/SQLAlchemy. One DB file = one resumable environment.
- **Coordinator UI** ("site office"): small React app showing the board, the single surfaced line, and the one-tap gate. Talks to the orchestrator over WebSocket (live board) + REST (approve/dismiss).
- **Runner**: `docker-compose` or a `Makefile` that boots all portals + orchestrator + UI with one command.

---

## Repo layout

```
/portals
  /tms            # EXISTS — do not rebuild
  /carrier        # EXISTS — do not rebuild
  /customs        # BUILD
  /terminal       # BUILD — no-feed; detention only visible with the ref code
/agent
  /orchestrator   # state machine, event loop, gate policy
  /monitoring     # alert engine + free-time-clock rules
  /computer_use   # Gemini CU <-> Playwright harness
  /voice          # Live Translate channel (+ DEMO fallback)
  /board          # SQLite models, migrations, resume(env_id)
  /audit          # artifact + action-log writer
/ui               # coordinator "site office"
/seed             # scenario data (MSKU4471 + others)
/scripts          # make demo, reset, kill/resume helpers
CLAUDE.md
MASTER_PROMPT.md
.env.example
```

---

## Commands

- `make demo` — boot everything, seed the scenario, open the coordinator UI.
- `make reset` — wipe the board DB and re-seed (deterministic).
- `make kill` / `make resume` — stop the orchestrator mid-run / re-hydrate from the same DB (proves invariant 4).
- `make test` — unit tests (state machine transitions, alert engine, gate policy) + the golden-path integration test.

---

## Coding standards

- **Typed and small.** Type hints everywhere in Python; small pure functions for the state machine and alert engine (they must be unit-testable without the network).
- **The portals are untrusted UIs.** Treat CU's parsed observations as untrusted input; validate before writing to the board. Never let portal text drive a high-cost action without the human gate.
- **Deterministic demo.** Seeded data, fixed clocks in `DEMO_MODE`, LT fallback ready. The golden path must run the same way every time.
- **Idempotent transitions.** Every state transition writes to SQLite before side effects, so a crash resumes cleanly.
- **No secrets in code.** Keys via `.env` (see `.env.example`). Portal "credentials" are `DEMO-ONLY` fixtures.
- **Log then act.** Audit-write happens before the action executes and after it verifies (screenshot both).

## Definition of done (per component)

A component is done when: it has a unit test (or an integration step) that exercises it, it respects all seven invariants, and its `DEMO-ONLY` shortcuts are labeled. The **project** is done when `make demo` runs the golden path end-to-end (see MASTER_PROMPT.md, "Acceptance") including a live `kill`/`resume`.
