from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .browser_hands import BrowserHands
from .safety_gate import SafetyBlockedError, SafetyGate
from .schemas import ActionResult, collect_model_text, iter_function_calls


class CircuitBreakerError(RuntimeError):
    pass


@dataclass
class BrainRunResult:
    completed: bool
    final_text: str = ""
    turns: int = 0


class GeminiComputerUseBrain:
    """Layer 1: Gemini Computer Use loop controller."""

    def __init__(
        self,
        *,
        hands: BrowserHands,
        safety_gate: SafetyGate,
        model: str = "gemini-3.5-flash",
        max_turns: int = 25,
        max_error_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        self.hands = hands
        self.safety_gate = safety_gate
        self.model = model
        self.max_turns = max_turns
        self.max_error_retries = max_error_retries
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    async def run(self, goal: str) -> BrainRunResult:
        initial_screenshot = await self.hands.screenshot_base64()
        interaction = await self._create_interaction(
            input_payload=[
                {"type": "text", "text": self._system_goal(goal)},
                {"type": "image", "data": initial_screenshot, "mime_type": "image/png"},
            ]
        )

        consecutive_errors = 0
        for turn in range(1, self.max_turns + 1):
            print(f"\n[brain] turn {turn}")
            commands = list(iter_function_calls(interaction))
            if not commands:
                final_text = collect_model_text(interaction)
                print(f"[brain] completed: {final_text}")
                return BrainRunResult(completed=True, final_text=final_text, turns=turn)

            results: list[ActionResult] = []
            for command in commands:
                print(f"[brain] proposed {command.name}: {command.arguments}")
                try:
                    gate_decision = await self.safety_gate.validate(command, self.hands)
                    for note in gate_decision.notes:
                        print(f"[gate] {note}")
                    execution_payload = await self.hands.execute(gate_decision.command)
                    error_text = await self.hands.inspect_errors()
                except SafetyBlockedError:
                    raise
                except Exception as exc:
                    results.append(
                        ActionResult(
                            name=command.name,
                            call_id=command.call_id,
                            payload={"status": "execution_error", "error": str(exc), "url": self.hands.url},
                        )
                    )
                    continue

                payload: dict[str, Any] = {
                    "status": "executed",
                    "url": self.hands.url,
                    **execution_payload,
                }
                if gate_decision.safety_acknowledgement:
                    payload["safety_acknowledgement"] = True

                if error_text:
                    consecutive_errors += 1
                    payload["post_action_error"] = error_text
                    payload["correction_prompt"] = (
                        "The page shows an error after the last action. "
                        "Use the screenshot and this error text to correct the workflow."
                    )
                    print(f"[checker] detected page error: {error_text}")
                    if consecutive_errors >= self.max_error_retries:
                        raise CircuitBreakerError(
                            f"Circuit breaker opened after {consecutive_errors} consecutive page errors: {error_text}"
                        )
                else:
                    consecutive_errors = 0

                results.append(ActionResult(name=command.name, call_id=command.call_id, payload=payload))

            function_responses = await self._build_function_responses(results)
            interaction = await self._create_interaction(
                input_payload=function_responses,
                previous_interaction_id=getattr(interaction, "id", None)
                or (interaction.get("id") if isinstance(interaction, dict) else None),
            )

        raise CircuitBreakerError(f"Turn limit reached: {self.max_turns}")

    def _system_goal(self, goal: str) -> str:
        return (
            "You are Docklock, an autonomous logistics browser agent. "
            "Work only inside the visible local logistics portals. "
            "Do not directly perform consequential actions without allowing safety confirmation. "
            f"Goal: {goal}"
        )

    async def _create_interaction(
        self,
        *,
        input_payload: list[dict[str, Any]],
        previous_interaction_id: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": input_payload,
            "tools": [
                {
                    "type": "computer_use",
                    "environment": "browser",
                    "enable_prompt_injection_detection": True,
                }
            ],
        }
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id

        return await asyncio.to_thread(self.client.interactions.create, **kwargs)

    async def _build_function_responses(self, results: list[ActionResult]) -> list[dict[str, Any]]:
        screenshot = await self.hands.screenshot_base64()
        responses: list[dict[str, Any]] = []
        for result in results:
            responses.append(
                {
                    "type": "function_result",
                    "name": result.name,
                    "call_id": result.call_id,
                    "result": [
                        {
                            "type": "text",
                            "text": json.dumps(result.payload),
                        },
                        {
                            "type": "image",
                            "data": screenshot,
                            "mime_type": "image/png",
                        },
                    ],
                }
            )
        return responses

