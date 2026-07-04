# Unblock — Project Status

_Living status doc. Last updated: **2026-07-05**. Branch: **`agentic-system`**._
_See [CLAUDE.md](CLAUDE.md) for architecture/invariants and [MASTER_PROMPT] spec (§ refs below)._

## Milestones

| # | Milestone | State | Proof |
|---|---|---|---|
| M1 | Orchestration skeleton (board, monitoring, state machine, gate, UI) — stubs for CU/voice | ✅ done | `make test` 9/9, `make golden` incl. live kill/resume |
| M2 | Real Gemini Computer Use + Playwright; carrier/terminal portals | ✅ done | live full golden path under `CU_MODE=real`; `make cu-smoke` |
| M3 | Real Live Translate voice — integrate the `twilio` branch (+ scripted fallback) | ⬜ next | — |
| M4 | Audit polish, hardening, MASTER_PROMPT.md, final pass | ⬜ pending | — |

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

## Commands

| Command | Purpose |
|---|---|
| `make setup` | install Python + Node deps + Playwright Chromium |
| `make demo` | boot portals + orchestrator + UI (**stub** CU — deterministic) |
| `make demo-cu` | same, with **real** Gemini Computer Use (needs `GEMINI_API_KEY` + display) |
| `make cu-smoke` | one live CU read of the terminal portal (Vite server must be up) |
| `make golden` | drive golden path 1→9 via the public API incl. live kill/resume (stub) |
| `make test` | acceptance tests §12 (9/9, offline) |
| `make build` / `make lint` | typecheck+build all Vite pages / oxlint |
| `make reset` | wipe board DB + artifacts + browser profile, re-seed |

## Architecture snapshot

- **Orchestrator** (FastAPI) `:5000` — REST + `WS /board/stream` + `/artifacts`. Only interface the UI uses.
- **Vite** `:5173` — all portal pages + Site Office: `ui.html`, `tms.html`, `index.html`
  (customs), `carrier.html`, `terminal.html`.
- **CU_MODE** env: `stub` (default; tests + `make golden`) | `real` (`make demo-cu`). Falls back to stub on failure.
- **Toolchain:** Python 3.12 (`.venv`), Node 22 via `nvm` (Vite 8 needs ≥20), `google-genai` 2.10, Playwright 1.61.

## Known DEMO-ONLY / risks

- Portals are **unauthenticated** (no forwarder login to script). Prod would need real login.
- Real CU preview is slow/rate-limited → stub is the safe default for tests/golden; turn cap + retries.
- DOM `data-field` extraction is used for **reliable** field parsing (the model still does the operating).
- Voice is still the **stub** (scripted `DET-4471-B`) until M3.
- `.env` holds live-looking secrets — gitignored, only `.env.example` is committed.

## Next steps (M3)

1. Port `twilio_gemini_bridge.py` + `tools/gate.py` from the `twilio` branch under `/agent/voice`.
2. Wrap the bridge → `voice.take_call() -> FieldTruth`; emit an `EVENT` to the orchestrator on tool-call.
3. Ship the scripted fallback (`seed/driver_es.wav` + transcript) so the demo never needs a live mic.
4. `voice.callback()` speaks the Spanish resolution back.

## Changelog

- **2026-07-05** — M2 done: real Gemini Computer Use + Playwright, carrier/terminal portals,
  `CU_MODE` switch. Committed on `agentic-system` (`48901f7`). Added this STATUS.md.
- **2026-07-04** — M1 done: board/monitoring/orchestrator/UI + CU & voice stubs; golden path
  green with live kill/resume.
