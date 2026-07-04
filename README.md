# Docklock Autonomous Logistics Agent

Docklock is a Python backend and automation engine for a Google/DeepMind hackathon logistics demo.

It solves a common supply-chain problem: important freight data is split across old web portals that do not expose APIs. Docklock lets an AI agent inspect those portals through a browser, but it does not let the AI click or type freely. Every action must pass through deterministic safety middleware first.

The target demo container is:

```text
MSKU4471
```

## The Short Version

Docklock has three layers:

```text
Layer 1: The Brain       Gemini 3.5 Flash Computer Use
Layer 2: The Safety Gate Deterministic Python middleware
Layer 3: The Hands       Playwright browser automation
```

The most important rule:

```text
Gemini proposes actions. Docklock verifies them. Playwright executes only approved actions.
```

Gemini never clicks the browser directly.

## Why This Exists

In a fragmented freight workflow, one portal may say a container is ready, another portal may show a customs rejection, and a terminal portal may reveal an unpaid fee. A normal automation script cannot reason across all of this. An AI agent can reason across screenshots, but it can also make risky guesses.

Docklock is built to prevent those risky guesses, especially when the AI tries to:

- invent a customs tariff code
- edit physical container data to make mismatched records agree
- pay an unexpected fee just to complete the task
- navigate outside the trusted demo portals

## Key Terms

### DOM

DOM means **Document Object Model**. It is the browser's internal tree of the page: buttons, inputs, tables, text, labels, links, and form fields.

Gemini may propose:

```text
click(x=520, y=410)
```

Before Playwright clicks, Docklock asks the browser what is actually under that coordinate:

```js
document.elementFromPoint(x, y)
```

If that coordinate points to a button like `Pay Total Balance` or `Validate & Re-submit`, the Safety Gate can pause the action.

### HITL

HITL means **Human-in-the-Loop**.

When Docklock sees a risky action, it freezes the browser loop and asks a human for approval. This is used for actions like payment, submission, confirmation, or unrecognized business data.

Example:

```text
AI proposes: Click "Pay Total Balance: $465.00"
Safety Gate sees: $340 detention fee + $125 X-Ray fee
PO ledger allows: $340 detention only
Docklock pauses: Human approval required
```

## Architecture

```text
Gemini screenshot analysis
        |
        v
Proposed function_call
click/type/scroll/navigate
        |
        v
Safety Gate checks:
native safety, DOM target, business rules, HITL, network boundary
        |
        v
Playwright executes only if approved
        |
        v
New screenshot goes back to Gemini
```

## Project Structure

```text
.
├── README.md
├── docs/
│   └── architecture.md
├── pyproject.toml
├── src/
│   └── docklock/
│       ├── brain_controller.py   # Layer 1: Gemini Computer Use loop
│       ├── safety_gate.py        # Layer 2: deterministic safety middleware
│       ├── browser_hands.py      # Layer 3: Playwright browser execution
│       ├── main.py               # CLI entrypoint
│       ├── schemas.py            # shared action/result/HITL data models
│       └── __init__.py
└── tests/
    └── test_safety_gate.py
```

## Implemented Safety Layers

### 1. Native Gemini Safety Routing

Docklock reads Gemini's native `safety_decision`.

Behavior:

- `regular`: continue to Docklock's local checks
- `require_confirmation`: pause for human approval
- `blocked`: terminate the action immediately

When a human approves a Gemini confirmation request, Docklock sends back:

```json
{
  "safety_acknowledgement": true
}
```

### 2. DOM Coordinate Resolution

Gemini Computer Use works with normalized coordinates from `0` to `999`.

Docklock scales those coordinates to the real browser viewport, then resolves the real DOM element at that point before clicking.

This prevents blind coordinate execution.

### 3. High-Risk Keyword Intercept

If the DOM target contains risky words, Docklock pauses for HITL approval.

Current triggers include:

```text
pay
payment
submit
validate & re-submit
delete
override
confirm
release cargo
```

This check can override Gemini's own `regular` decision.

### 4. Customs HS Code Guard

On the Customs / ICS2 portal, Docklock restricts typing to valid 2026 HS code format:

```text
dddd.dd.dd
```

Example:

```text
8517.13.00
```

Docklock also checks the code against the approved company catalog. The demo catalog currently allows:

```text
8517.13.00
```

If Gemini tries to type a sentence like:

```text
The correct code is probably 9999.99.99
```

Docklock blocks or pauses it instead of letting the AI guess legal customs data.

### 5. Physical Manifest Lock

Docklock permanently blocks AI edits to physical container facts:

```text
vgmWeight
sealNumber
containerId
```

This protects against the "brainstorming trap" where the AI sees:

```text
TMS weight: 22,400 KG
Carrier scale weight: 23,100 KG
Difference: +700 KG
```

and tries to solve the mismatch by editing the internal manifest. Docklock does not allow that.

### 6. Payment and PO Ledger Check

Before payment clicks, Docklock scrapes visible invoice line items from the page and compares them against a local authorized PO ledger.

Default authorized ledger:

```text
$340.00 detention fee
```

If the terminal portal shows:

```text
$340.00 Detention Fee
$125.00 X-Ray Inspection Fee
$465.00 Total Balance
```

Docklock detects the unbudgeted `$125.00` fee and pauses:

```text
UNBUDGETED_FEE_DETECTED
```

### 7. Network Allowlist

The Safety Gate and Playwright wrapper both enforce a strict browser boundary.

Default allowed origin:

```text
http://localhost:3000
```

If Gemini tries to navigate to an external website, Docklock blocks the request before execution.

### 8. Post-Action Error Checker

After an approved action runs, Docklock checks the page for error banners and rejection states, such as:

```text
DECLARATION: REJECTED
.error-message
[role="alert"]
```

If errors repeat too many times, Docklock opens a circuit breaker instead of looping forever.

## HITL Alert Payload

Every human approval pause emits a dashboard-ready JSON payload.

Example:

```json
{
  "status": "PAUSED_FOR_HITL",
  "timestamp": "2026-07-05T10:14:22Z",
  "container_id": "MSKU4471",
  "intercept_reason": "UNBUDGETED_FEE_DETECTED",
  "gemini_proposal": {
    "action": "click",
    "coordinates": {"x": 520, "y": 410},
    "native_safety_decision": "regular"
  },
  "dom_resolution": {
    "element_tag": "BUTTON",
    "element_text": "[ Pay Outstanding Detention & Release Cargo ]",
    "target_portal": "Hyper-Local Terminal Gate"
  },
  "business_context": "Unbudgeted line item detected: $125.00 (X-Ray Inspection Fee). No matching PO found. Do you authorize this expense?",
  "required_action": "1-TAP_HUMAN_APPROVAL"
}
```

## Demo Scenario

Docklock is designed around this multi-portal conflict:

1. **Legacy TMS** says container `MSKU4471` is ready to lift.
2. **Carrier Portal** shows transit status but reveals a physical weight mismatch.
3. **Customs ICS2** shows a rejected declaration caused by outdated HS code `8517.12.00`.
4. Docklock allows the approved corrected code `8517.13.00`.
5. The AI tries to submit the customs update. Docklock pauses for HITL.
6. **Terminal Gate** shows a payment requirement.
7. Docklock detects an unexpected `$125.00` X-Ray fee in addition to the authorized `$340.00` detention fee.
8. Human approval is required before the payment click can happen.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
export GEMINI_API_KEY="your-key"
```

## Run

Run against local demo portals:

```bash
docklock \
  --start-url http://localhost:3000 \
  --goal "Analyze container MSKU4471 across all tabs and resolve any holds"
```

Controlled hackathon demo mode with automatic approvals:

```bash
docklock --auto-approve-hitl
```

Send HITL alerts to a dashboard WebSocket:

```bash
docklock --hitl-websocket-url ws://localhost:8787/hitl
```

The WebSocket should return:

```json
{
  "approved": true
}
```

## Test

```bash
pytest -q
```

Current test coverage focuses on the deterministic Safety Gate:

- native safety blocking
- native confirmation HITL alert generation
- DOM high-risk action interception
- HS code sanitation and allowlisting
- immutable physical manifest blocking
- unbudgeted terminal fee detection
- external navigation blocking

## More Detail

See [docs/architecture.md](docs/architecture.md) for the deeper architecture and implementation notes.
