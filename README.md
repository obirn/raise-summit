# Docklock Autonomous Logistics Agent

Docklock is a three-layer backend for a zero-API logistics automation demo:

1. **Layer 1: The Brain** - Gemini 3.5 Flash Computer Use proposes browser actions from screenshots.
2. **Layer 2: The Safety Gate** - deterministic Python middleware validates every proposed action.
3. **Layer 3: The Hands** - Playwright executes only approved actions inside an allowlisted Chromium sandbox.

The important invariant is simple: **Gemini never touches Playwright directly.** All proposed `function_call` actions are converted to `ActionCommand`, validated by `SafetyGate`, then executed by `BrowserHands`.

## File Tree

```text
.
├── README.md
├── docs/
│   └── architecture.md
├── pyproject.toml
├── src/
│   └── docklock/
│       ├── __init__.py
│       ├── brain_controller.py
│       ├── browser_hands.py
│       ├── main.py
│       ├── safety_gate.py
│       └── schemas.py
└── tests/
    └── test_safety_gate.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
export GEMINI_API_KEY="your-key"
```

Run against the local mock portals at `http://localhost:3000`:

```bash
docklock --start-url http://localhost:3000 --goal "Analyze container MSKU4471 across all tabs and resolve any holds"
```

For hackathon demo mode where HITL confirmations are automatically approved:

```bash
docklock --auto-approve-hitl
```

To send HITL alerts to a dashboard WebSocket:

```bash
docklock --hitl-websocket-url ws://localhost:8787/hitl
```

## Safety Gates

Docklock implements defense-in-depth safety checks:

- Native Gemini `safety_decision`: `blocked` halts; `require_confirmation` pauses for HITL approval.
- DOM coordinate resolution: `document.elementFromPoint()` maps normalized model coordinates to a real DOM target before clicking.
- High-risk keyword intercept: clicks on text like `pay`, `submit`, `validate & re-submit`, `delete`, `override`, and `confirm` require approval.
- HS-code sanitation and allowlisting: Customs Portal typing is constrained to `dddd.dd.dd` and must match the approved company catalog, currently `8517.13.00`.
- Physical manifest lock: `vgmWeight`, `sealNumber`, and `containerId` cannot be edited by the AI, even when it finds a TMS/Carrier discrepancy.
- Terminal payment reconciliation: payment buttons trigger invoice scraping and local PO ledger matching. Docklock authorizes only the expected `$340.00` detention fee by default, so an extra `$125.00` X-Ray fee pauses for HITL.
- Network boundary enforcement: both the Safety Gate and Playwright wrapper block navigation outside the configured local demo origins.
- Checker-corrector loop: post-action DOM error banners are sent back to Gemini, with a circuit breaker after 3 repeated errors.

Every pause emits a dashboard-ready HITL payload:

```json
{
  "status": "PAUSED_FOR_HITL",
  "container_id": "MSKU4471",
  "intercept_reason": "UNBUDGETED_FEE_DETECTED",
  "required_action": "1-TAP_HUMAN_APPROVAL"
}
```

See [docs/architecture.md](/Users/mac/Documents/SafetyLayer/docs/architecture.md) for implementation details.
