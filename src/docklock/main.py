from __future__ import annotations

import argparse
import asyncio
import sys

from .brain_controller import CircuitBreakerError, GeminiComputerUseBrain
from .browser_hands import BrowserHands, NavigationBlockedError
from .safety_gate import AutoApprovalProvider, SafetyBlockedError, SafetyGate, TerminalApprovalProvider


DEFAULT_GOAL = "Analyze container MSKU4471 across all tabs and resolve any holds."


async def main_async(args: argparse.Namespace) -> int:
    approval = AutoApprovalProvider() if args.auto_approve_hitl else TerminalApprovalProvider()
    gate = SafetyGate(approval)

    async with BrowserHands(
        start_url=args.start_url,
        allowed_origins=tuple(args.allowed_origin),
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height,
        headless=args.headless,
    ) as hands:
        print("[main] Docklock online")
        print("[main] Layer 1: Gemini Computer Use")
        print("[main] Layer 2: deterministic Safety Gate")
        print("[main] Layer 3: Playwright Hands")
        print(f"[main] allowed origins: {args.allowed_origin}")
        print(f"[main] goal: {args.goal}")

        brain = GeminiComputerUseBrain(
            hands=hands,
            safety_gate=gate,
            model=args.model,
            max_turns=args.max_turns,
        )
        result = await brain.run(args.goal)
        print(f"[main] finished after {result.turns} turns")
        if result.final_text:
            print(f"[main] final: {result.final_text}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Docklock autonomous logistics agent.")
    parser.add_argument("--start-url", default="http://localhost:3000")
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=["http://localhost:3000"],
        help="Allowed browser origin. Repeat to add more local mock portals.",
    )
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--viewport-width", type=int, default=1440)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--auto-approve-hitl",
        action="store_true",
        help="Auto-approve human checkpoints. Use only for controlled demos.",
    )
    return parser


def cli() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main_async(args)))
    except KeyboardInterrupt:
        print("\n[main] interrupted")
        raise SystemExit(130)
    except (SafetyBlockedError, NavigationBlockedError, CircuitBreakerError) as exc:
        print(f"[main] stopped: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    cli()

