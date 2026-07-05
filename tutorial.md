# Tutorial — running the Unblock demo

This walks you from zero to the full **wow demo**: a real phone call in the driver's language →
a durable Antigravity agent reasons → Gemini Computer Use operates the closed portal → a human
one-tap approval → the driver is told over the phone → the container is released.

There are three tiers. Start at the top; each adds one live primitive.

1. [Offline demo](#1-offline-demo-no-key-needed) — deterministic, no API key, no browser.
2. [Real Computer Use + agent](#2-real-computer-use--durable-agent) — the agent actually clicks.
3. [Full wow demo](#3-full-wow-demo-phone--antigravity--computer-use--voice-back) — real phone call + speak-back.

---

## Prerequisites

- **Python 3.12** (the repo's `.venv`) and **Node ≥ 20** (Node 22 via `nvm`; `scripts/env.sh`
  loads it).
- A `GEMINI_API_KEY` in `.env` (copy from `.env.example`). Needed from tier 2 on.
- A **display** (headful Chromium) for real Computer Use.
- For tier 3: a **Twilio** phone number and **ngrok** (both `DEMO-ONLY`).

One-time setup:

```bash
cp .env.example .env      # fill GEMINI_API_KEY (+ TWILIO_* for tier 3)
make setup                # Python deps + Playwright Chromium + npm install
```

> **Golden rule:** never start a stack while a previous one is still running. `demo.sh` now
> auto-cleans stale orchestrators and the Computer Use browser on start, but if in doubt run
> `make stop` first. Stacked instances fighting over port `5000` and the `.cu_profile` lock is the
> #1 cause of a frozen demo.

---

## 1. Offline demo (no key needed)

Deterministic, network-free — good for a first look and for CI.

```bash
make stop && make reset
make demo
```

Open the **Site Office**: http://localhost:5173/ui.html

In the Site Office:

1. Click **Run tick** — the alert engine fires on held state (no portal was read yet) and the
   board shows `MSKU4471` going into diagnosis.
2. Click **Driver calls in** — a scripted Spanish↔English call yields the reference; the terminal
   read reveals **$340**; a one-tap **Pay & release** appears.
3. Click **Pay & release** — the container moves to `released`. Open the **audit** toggle on a row
   to see the screenshot trail.

Prove durability at any point:

```bash
make kill      # stop the orchestrator mid-run
make resume    # re-hydrate from SQLite — nothing is lost (invariant 4)
```

---

## 2. Real Computer Use + durable agent

Now the agent actually **sees and clicks** the portals, planned by a durable Antigravity agent.

```bash
make stop && make reset
AGENT_MODE=agentic AGENT_BRAIN=antigravity ANTIGRAVITY_VARIANT=model CU_MODE=real bash scripts/demo.sh
```

- `CU_MODE=real` → a headful Chromium window opens; **keep it visible**, that is the audience's
  proof the agent operates the portal like a human.
- `AGENT_BRAIN=antigravity ANTIGRAVITY_VARIANT=model` → the planner's reasoning lives in a durable
  Gemini **Interaction**, resumed by id. The `model` variant is fast (~4 s/decision) and has no
  remote sandbox, while remaining durable. (`ANTIGRAVITY_VARIANT=agent` is the literal managed
  Antigravity agent — more faithful but ~15 s/decision.)

Drive it from the Site Office exactly as in tier 1 (**Run tick** → **Driver calls in** →
**Pay & release**), and watch the Chromium window read each portal, type the reference, reveal
$340, and click Pay & release. Each agent card shows its **step timeline** and a
`⛓ durable via Antigravity` badge.

### The durability money-shot

While an agent is `awaiting_human` (a surfaced approval is on screen):

```bash
make kill                                                   # process dies; the board keeps only the interaction id
AGENT_MODE=agentic AGENT_BRAIN=antigravity ANTIGRAVITY_VARIANT=model CU_MODE=real make resume
```

Then click **Pay & release**. The agent **resumes the same server-side interaction by id** and
finishes the fix. The line to say:

> "The agent's memory of this exception isn't in our database — it's a durable Antigravity
> interaction, resumed by id. We kill the infrastructure, and it remembers."

---

## 3. Full wow demo (phone → Antigravity → Computer Use → voice back)

Adds the **real phone call** and the **spoken confirmation back to the driver**.

### Launch (three terminals)

```bash
# Terminal A — orchestrator: agentic + real Computer Use + speak-back
make stop && make reset
AGENT_MODE=agentic AGENT_BRAIN=antigravity ANTIGRAVITY_VARIANT=model \
  CU_MODE=real VOICE_MODE=bridge bash scripts/demo.sh

# Terminal B — the Twilio <-> Gemini-Live bridge
make voice

# Terminal C — expose the bridge to Twilio
ngrok http 8080
```

Then point your **Twilio number's Voice webhook** at `https://<ngrok-id>/voice` (`DEMO-ONLY`).

On screen: the **Site Office** (http://localhost:5173/ui.html) and the **Computer Use Chromium
window**.

> **Do not click "Run tick"** for this run. Let the phone call be the *only* trigger — one agent,
> no slow parallel sweep.

### The run

| Step | You do | You show | You say |
|---|---|---|---|
| 1 | Open the Site Office | the board, `MSKU4471`, the timers | "The agent watches a portfolio of containers. Detection is **time-math on held state** — zero polling." |
| 2 | **Call** the Twilio number | "Driver on the line" + live transcript | "**Live Translate**, two-way, cross-language." |
| 3 | Say: *"Container **MSKU4471**, blocked at the Valencia gate."* then, when asked: *"Reference **DET-4471-B**."* | the transcript filling in | "This reference exists **only** in the driver's voice — no portal exposes it." |
| 4 | Let the agent work | the **agent card** timeline + the **Chromium** window typing the reference and clicking Look up → **$340** | "The agent reasons durably, then **Gemini Computer Use** operates the closed portal like a human — the only way in, no API." |
| 5 | — | the **single line**: *"MSKU4471 — unpaid terminal detention $340. Driver waiting."* + **Pay & release** | "Every high-cost action is **human-gated**: one line, one tap." |
| 6 | **Click Pay & release** | Computer Use clicks Pay & release → verifies → **`released`**; the audit shows before/after screenshots | "The agent executes and **verifies**. The audit trail is demurrage-dispute evidence." |
| 7 | — | the driver **hears the confirmation over the phone, in their language** | "And the loop closes: the driver is told, by voice, that it's paid and they can pass." |

### The one-sentence pitch (the three primitives chained)

> "**Live Translate** delivers the reference only the voice knows → **Antigravity** holds and
> resumes the agent's reasoning across the long horizon → **Computer Use** acts on the closed
> portal. The second primitive only fires because the first is already running. None is decorative."

---

## Safety nets (if live gets flaky)

- **No phone / ngrok** → use the Site Office **"Driver calls in"** button (scripted voice, *same*
  code path).
- **Computer Use slow or unstable** → `CU_MODE=stub` (instant dispatch, no browser).
- **Antigravity API hiccup** → the brain automatically falls back to a local Gemini
  function-calling brain; the demo never stalls. (`AGENT_BRAIN=gemini` forces that path outright.)
- **Frozen demo** → almost always stale processes. `make stop && make reset`, then relaunch.
  Never run `make stop` *during* a run — it kills the Computer Use browser.
- **Driver's reference mangled by ASR** (e.g. `DET447.1B`) → the terminal matches references
  tolerantly (dashes/dots/spaces ignored), so it still resolves.

---

## Configuration cheat-sheet

| Var | Demo value | Why |
|---|---|---|
| `AGENT_MODE` | `agentic` | Spawn durable solver agents. |
| `AGENT_BRAIN` | `antigravity` | Durable reasoning via the Interactions API. |
| `ANTIGRAVITY_VARIANT` | `model` | Fast + durable (no remote sandbox). Use `agent` for the literal managed agent. |
| `CU_MODE` | `real` | Real Computer Use clicks (needs a display). |
| `VOICE_MODE` | `bridge` | Speak the resolution back into the open call. |
| `VAD_SILENCE_MS` | `550` | Lower = the agent replies sooner; raise it in a noisy gate. |

See [README.md](README.md) for the full switch table and [CLAUDE.md](CLAUDE.md) for the seven
invariants and confirmed API details.
