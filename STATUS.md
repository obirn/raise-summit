# Unblock — Project Status

_Living status doc. Last updated: **2026-07-05**. Branch: **`agentic-system`**._
_See [CLAUDE.md](CLAUDE.md) for architecture/invariants and [MASTER_PROMPT] spec (§ refs below)._

## Milestones

| # | Milestone | State | Proof |
|---|---|---|---|
| M1 | Orchestration skeleton (board, monitoring, state machine, gate, UI) — stubs for CU/voice | ✅ done | `make test` 9/9, `make golden` incl. live kill/resume |
| M2 | Real Gemini Computer Use + Playwright; carrier/terminal portals | ✅ done | live full golden path under `CU_MODE=real`; `make cu-smoke` |
| M3 | Real Live Translate voice — Twilio↔Gemini-Live bridge integrated | ✅ done | phone-tested (user) + live push path `field-truth`→`resolving`; 12/12 tests |
| M5 | Agentic layer — orchestrator spawns durable solver agents that drive Computer Use | ✅ done | 15/15 tests; real Gemini planner surfaced $340 live; Antigravity API reachable |
| M6 | Antigravity Interactions API = the *load-bearing* durable brain (resume-by-id) | ✅ done | 17/17 tests (offline resume-by-id); real `antigravity-preview-05-2026` handoff live |
| M4 | Audit polish, hardening, MASTER_PROMPT.md, final pass | ⬜ next | — |

## What works today (verified)

- **Detection** = time-math on held state, zero portal reads (invariant 2). `tick()` fires
  `OVERDUE(gate_out)` for MSKU4471.
- **Computer Use is real** (`gemini-2.5-computer-use-preview-10-2025`): the model drives a
  headful browser and operates all four portals through their UI (invariant 1 — no backend).
- **Golden path 1→9** end-to-end: reads terminal/tms/carrier/customs → `stalled_unlocatable`
  → driver call (stub voice) supplies `DET-4471-B` → targeted terminal read reveals **$340**
  → human `/approve` gate → CU clicks **Pay & release**, re-reads to verify → `resolving`.
- **Invariant 6** holds in the real path: terminal shows nothing without the reference.
- **Decoy** TCLU3380: screen-only customs HS-code hold, resolved via CU (no voice).
- **Resumable state** (invariant 4): SQLite board, `make kill`/`resume` loses nothing.
- **Audit trail** (invariant 5): every read/act logs a screenshot; rendered in the UI.
- **Live Translate voice** (invariant 6): real Twilio↔Gemini-Live bridge (`agent/voice/
  twilio_bridge.py`, phone-tested). On the driver's `flag_blocked_at_gate` tool-call it POSTs
  `/events/field-truth` → same flow as the scripted demo; also streams `call-started` +
  live transcript to the Site Office. Scripted `StubVoice` stays the offline default.
- **Agentic layer** (`AGENT_MODE=agentic`): the orchestrator **spawns one durable solver agent
  per stuck container** (parallel portfolio). Each agent reasons with Gemini function-calling
  (`agent/solver/`), drives **our** Computer Use to read/act on the portals, surfaces to the
  human gate, and persists its plan on the board (resumable by `agent_id` = "Antigravity").
  Two-tier: planner (`AGENT_MODEL`) decides, CU worker clicks. `ScriptedBrain` keeps it offline
  for tests; the real Gemini brain planned `read terminal(DET-4471-B)`→`surface $340` live. The
  deterministic state machine stays as the `AGENT_MODE=deterministic` fallback (12 tests).
- **Antigravity as the load-bearing durable brain** (`AGENT_BRAIN=antigravity`): the solver agent's
  *reasoning* lives inside a durable Gemini Interaction (`antigravity-preview-05-2026`). Each
  decision is a `function_call` handed back at `requires_action`; **our local CU executes it**, and
  we continue via `previous_interaction_id` (server keeps context, no history resent). The board
  persists only the interaction handles — so **kill the process and the agent's reasoning survives
  only because we resume the same server-side interaction by id**. That's the primitive, load-bearing
  (not bolted on): remove it and the agent can't resume its reasoning across the horizon. Verified
  live (real handoff: `read_portal(DET-4471-B)`, real interaction/environment ids) + offline
  (`FakeInteractions` proves resume-by-id with no history resend). Falls back to the local Gemini
  brain on any API error so the demo never stalls. `ANTIGRAVITY_VARIANT=agent|model` reliability lever.

## Commands

| Command | Purpose |
|---|---|
| `make setup` | install Python + Node deps + Playwright Chromium |
| `make demo` | boot portals + orchestrator + UI (**stub** CU — deterministic) |
| `make demo-cu` | same, with **real** Gemini Computer Use (needs `GEMINI_API_KEY` + display) |
| `make cu-smoke` | one live CU read of the terminal portal (Vite server must be up) |
| `make voice` | run the Twilio↔Gemini-Live bridge `:8080` (DEMO-ONLY: needs ngrok + Twilio number) |
| `make agentic` | demo with LLM solver agents (`AGENT_MODE=agentic`; add `CU_MODE=real` for real clicks) |
| `make antigravity-probe` | check if the experimental `antigravity-preview-05-2026` agent is reachable |
| `make golden` | drive golden path 1→9 via the public API incl. live kill/resume (stub) |
| `make test` | acceptance tests §12 (9/9, offline) |
| `make build` / `make lint` | typecheck+build all Vite pages / oxlint |
| `make reset` | wipe board DB + artifacts + browser profile, re-seed |

## Architecture snapshot

- **Orchestrator** (FastAPI) `:5000` — REST + `WS /board/stream` + `/artifacts`. Only interface the UI uses.
  Push endpoints for the voice bridge: `/events/{call-started,transcript,field-truth}`.
- **Voice bridge** (FastAPI) `:8080` — Twilio Media Streams `/voice` (TwiML) + `/ws` ↔ Gemini Live.
- **Vite** `:5173` — all portal pages + Site Office: `ui.html`, `tms.html`, `index.html`
  (customs), `carrier.html`, `terminal.html`.
- **CU_MODE** env: `stub` (default; tests + `make golden`) | `real` (`make demo-cu`). Falls back to stub on failure.
- **Toolchain:** Python 3.12 (`.venv`), Node 22 via `nvm` (Vite 8 needs ≥20), `google-genai` 2.10, Playwright 1.61.

## Known DEMO-ONLY / risks

- Portals are **unauthenticated** (no forwarder login to script). Prod would need real login.
- Real CU preview is slow/rate-limited → stub is the safe default for tests/golden; turn cap + retries.
- DOM `data-field` extraction is used for **reliable** field parsing (the model still does the operating).
- Real telephony needs **ngrok + a Twilio number** (`make voice`) — DEMO-ONLY; `make demo` uses the
  scripted `StubVoice` (deterministic, offline). `voice.callback` (spoken resolution back to the
  driver) is still a stub log — outbound/held-call callback is future work.
- `.env` holds live-looking secrets — gitignored, only `.env.example` is committed.

## Next steps (M4)

1. Polish the audit trail as a product surface (before/after screenshots as demurrage evidence).
2. Write `MASTER_PROMPT.md`; tidy CLAUDE.md; broaden tests/hardening.
3. Optional: real `voice.callback` (speak the resolution back into an active/outbound call);
   `seed/driver_es.wav` recorded track.

## Changelog

- **2026-07-05** — M6 done: Antigravity Interactions API made the *load-bearing* durable brain.
  `AntigravityBrain` (`agent/solver/brain.py`) seats the agent's reasoning in a durable interaction,
  continues by `previous_interaction_id` (no history resend), executes tools locally via CU; board
  holds only the handles → kill/resume continues the SAME server-side interaction. Verified live
  (real `antigravity-preview-05-2026` function-call handoff) + offline resume-by-id. 17/17 tests.
  Run: `make agentic AGENT_BRAIN=antigravity`.
- **2026-07-05** — M5 done: agentic layer. `AGENT_MODE=agentic` spawns durable solver agents
  (`agent/solver/{brain,agent,manager}.py`) that reason with Gemini function-calling and drive
  our Computer Use; human gate + board unchanged; "Agents at work" UI panel. 15/15 tests; real
  Gemini planner surfaced $340 live; `antigravity-preview-05-2026` probe reachable.
- **2026-07-05** — M3 bugfix (confirmed by live call): the bridge hung up right after the
  agent's turn (`session.receive()` ends at each `turn_complete`; the pump treated end-of-turn
  as end-of-call, and pump exceptions were re-raised silently → WS crash). Now re-loops
  `receive()` across turns and logs every teardown path (exceptions with traceback, Twilio
  events, turn boundaries, exit reasons; `LOG_LEVEL=DEBUG` for media frames). Multi-turn
  conversation works end to end.
- **2026-07-05** — M3 done: Twilio↔Gemini-Live bridge integrated under `agent/voice/` (relocated
  from the `twilio` branch), push path `/events/field-truth` + `call-started`/`transcript`, lazy
  Gemini client, `make voice`. Verified live push path → `resolving`; 12/12 tests.
- **2026-07-05** — M2 done: real Gemini Computer Use + Playwright, carrier/terminal portals,
  `CU_MODE` switch. Committed on `agentic-system` (`48901f7`). Added this STATUS.md.
- **2026-07-04** — M1 done: board/monitoring/orchestrator/UI + CU & voice stubs; golden path
  green with live kill/resume.
