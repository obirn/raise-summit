# Unblock

**Unblock is an agentic logistics system that resolves stuck-container exceptions for freight
forwarders.** When a container stops moving, the agent does not guess from a static snapshot. It
monitors durable shipment state, detects overdue milestones, and then investigates the issue by
operating the same closed portals a human coordinator would use.

Built for the **Google DeepMind** in-person hackathon. Three primitives, each load-bearing:

- **Gemini Computer Use** — sees a screen and clicks. The only way into systems with no API.
- **Antigravity (Interactions API)** — durable agent reasoning that survives process death and
  resumes *by id* across a long horizon.
- **Live Translate** — two-way, cross-language field voice, mid-call.

> This repo is a **demo with fake portals**. Every real-world concern that is stubbed (MFA,
> telephony, ToS, credentials, deterministic DOM reads) is marked `DEMO-ONLY` in the code.

---

## The scenario (golden path — container `MSKU4471`)

1. A milestone goes overdue. Detection is **deterministic time-math on held state** — no polling.
2. A durable **solver agent** is spawned. It reads every portal it has access to via Computer Use —
   TMS, carrier, customs, terminal — and finds them all clean.
3. The real blocker (a terminal **detention charge**) is **invisible on every portal**: it can only
   be surfaced with a reference the driver reads off the gate screen.
4. The **driver calls in**. Live Translate runs the two-way conversation (e.g. Spanish ↔ English)
   and extracts the exact reference `DET-4471-B`.
5. The agent does a **targeted terminal read** with that reference → reveals **$340 unpaid**.
6. It surfaces **one plain-language line + a one-tap approval** to the human coordinator. It never
   pays on its own.
7. On approval, Computer Use clicks **Pay & release**, then verifies the result.
8. The confirmation is **spoken back to the driver over the still-open call**, in their language.
9. The container reaches **`released`**. Every read and action is in the audit trail with a
   screenshot — doubling as demurrage-dispute evidence.

---

## The seven invariants

The whole design exists to hold these. See [CLAUDE.md](CLAUDE.md) for the full text.

1. **No backdoor.** The agent reaches portals *only* through their UI via Computer Use — never a
   portal API/DB. Portal state lives in the browser (localStorage); the agent has no other path in.
2. **Time triggers vision, never the reverse.** Detection is deterministic math; Computer Use runs
   only when the alert engine decides a read is worth its cost.
3. **Human gate on high-cost actions.** Pay/file/submit always surface one line + a one-tap approve
   *before* Computer Use executes. Reads are auto; writes are gated.
4. **The board is the single source of truth.** All state persists to SQLite; `resume(env_id)`
   re-hydrates losslessly. Kill the process mid-run and restart — nothing is lost.
5. **Audit trail is first-class.** Every observation and action is logged with a screenshot + timestamp.
6. **Live Translate is load-bearing** at the terminal blocker — the reference exists *only* in the
   driver's voice, on no monitored portal.
7. **Agent scope = forwarder scope.** The agent has exactly the access a forwarder employee has.

---

## Architecture

A single repo, three runtimes booted by a `Makefile`.

| Piece | What it is | Port |
|---|---|---|
| **Portals** | One Vite + React app, one HTML page per portal (`index.html` customs, `tms.html`, `carrier.html`, `terminal.html`). State is client-only (localStorage) — no backend, by design (invariant 1). | 5173 |
| **Site Office** | The coordinator UI (`ui.html`) — board, KPIs, the surfaced approval, live transcript, agent step-timelines. WS + REST to the orchestrator. | 5173 |
| **Orchestrator** | Python 3.12 / FastAPI. State machine, alert engine, board (SQLite), gate policy, Computer Use worker, solver agents. | 5000 |
| **Voice bridge** | Twilio ↔ Gemini-Live bridge. Push path on the driver's tool-call; speak-back into the open call on resolution. | 8080 |

**Two-tier agent:** a **planner** (`AGENT_BRAIN` — the durable Antigravity Interaction, a Gemini
function-calling brain, or an offline scripted brain) decides *what* to do; the **Computer Use
worker** does the *clicking*. This keeps our headful local browser (invariant 1) while the
reasoning can live durably server-side (resume-by-id).

```
/agent
  /orchestrator   state machine, event loop, gate policy, FastAPI
  /monitoring     alert engine + free-time clock (pure time math)
  /computer_use   Gemini Computer Use <-> Playwright (headful)
  /solver         durable solver agents + brains (scripted | gemini | antigravity)
  /voice          Twilio <-> Gemini-Live bridge + speak-back
  /board          SQLite models + resume(env_id)
  /audit          screenshot + action-log writer
/src              portals + Site Office (Vite pages)
/seed             scenario data (MSKU4471 + decoys)
/scripts + Makefile
```

---

## Quickstart

Requirements: **Python 3.12** (`.venv`), **Node ≥ 20** (this repo uses Node 22 via `nvm`), a
`GEMINI_API_KEY`. For the real phone call: a Twilio number + `ngrok`.

```bash
cp .env.example .env      # fill in GEMINI_API_KEY (+ TWILIO_* for real calls)
make setup                # Python deps + Playwright Chromium + npm install

make demo                 # boot everything (deterministic, stub Computer Use + voice)
```

Open the **Site Office** at http://localhost:5173/ui.html.

For the full agentic demo with real Computer Use and live voice, see **[tutorial.md](tutorial.md)**.

---

## Commands

| Command | What it does |
|---|---|
| `make demo` | Boot portals + orchestrator + Site Office (stub Computer Use — offline, deterministic). |
| `make agentic` | Same, but the orchestrator spawns durable solver agents (`AGENT_MODE=agentic`). |
| `make voice` | Run the Twilio ↔ Gemini-Live bridge on `:8080`. |
| `make reset` | Wipe the board DB + artifacts + browser profile and re-seed deterministically. |
| `make stop` | Full teardown: orchestrator + Vite + voice bridge + the Computer Use browser. |
| `make kill` / `make resume` | Stop the orchestrator mid-run / re-hydrate from SQLite (proves invariant 4). |
| `make test` | Unit + integration tests (offline, no network) — **17/17**. |
| `make build` / `make lint` | Typecheck + build all Vite pages / lint the frontend. |
| `make antigravity-probe` | Check the experimental Antigravity Interactions API is reachable. |

---

## Configuration switches

Set as environment variables (see [.env.example](.env.example)).

| Var | Values | Meaning |
|---|---|---|
| `CU_MODE` | `stub` \| `real` | Deterministic stub vs real Gemini Computer Use + Playwright (needs a display). |
| `AGENT_MODE` | `deterministic` \| `agentic` | Hardcoded diagnose vs LLM-planned durable solver agents. |
| `AGENT_BRAIN` | `scripted` \| `gemini` \| `antigravity` | The planner tier. |
| `ANTIGRAVITY_VARIANT` | `agent` \| `model` | Literal Antigravity managed agent (remote sandbox, slower) vs the Interactions API with a plain model (fast, no sandbox, **still durable resume-by-id**). |
| `VOICE_MODE` | `stub` \| `bridge` | Log-only callback vs speak the resolution back into the open live call. |

All defaults are offline and deterministic, so `make test` and `make demo` never need the network.

---

## Status

All milestones (M1–M6) are built and tested. The deterministic golden path, the durable
resume-by-id, real Computer Use, real Live Translate (both directions), and the agentic layer all
run. See [STATUS.md](STATUS.md) for the living breakdown and [CLAUDE.md](CLAUDE.md) for the
engineering conventions and confirmed API details.
