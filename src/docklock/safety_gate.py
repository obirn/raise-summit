from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Protocol

from .schemas import ActionCommand, DomTarget, GateDecision


HS_CODE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
HS_CODE_FIND_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}")

POINTER_ACTIONS = {
    "click",
    "click_at",
    "double_click",
    "triple_click",
    "middle_click",
    "right_click",
    "mouse_down",
    "mouse_up",
    "move",
    "long_press",
}


class SafetyBlockedError(RuntimeError):
    """Raised when a model-proposed action must not be executed."""


class ApprovalProvider(Protocol):
    async def request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
    ) -> bool:
        ...


@dataclass
class TerminalApprovalProvider:
    """Minimal HITL provider for terminal demos."""

    async def request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
    ) -> bool:
        print("\n[HITL] Human approval required")
        print(f"[HITL] Reason: {reason}")
        print(f"[HITL] Proposed action: {command.name} {command.arguments}")
        if dom_target:
            print(f"[HITL] DOM target: <{dom_target.tag}> {dom_target.text!r}")
        if safety_decision:
            print(f"[HITL] Native safety decision: {safety_decision}")

        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, input, "[HITL] Approve? [y/N] ")
        return answer.strip().lower() in {"y", "yes", "approve", "approved"}


@dataclass
class AutoApprovalProvider:
    """For controlled hackathon demos only."""

    async def request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
    ) -> bool:
        target = f" target=<{dom_target.tag}> {dom_target.text!r}" if dom_target else ""
        print(f"[HITL:auto-approved] {reason}; action={command.name}{target}")
        return True


class SafetyGate:
    def __init__(
        self,
        approval_provider: ApprovalProvider,
        high_risk_keywords: tuple[str, ...] | None = None,
    ) -> None:
        self.approval_provider = approval_provider
        self.high_risk_keywords = high_risk_keywords or (
            "pay",
            "payment",
            "submit",
            "validate & re-submit",
            "validate and re-submit",
            "delete",
            "override",
            "release cargo",
        )

    async def validate(self, command: ActionCommand, hands: object) -> GateDecision:
        notes: list[str] = []
        safety_acknowledgement = False
        dom_target: DomTarget | None = None
        sanitized_command = command

        if command.safety_decision:
            native_note = await self._check_native_safety(command)
            safety_acknowledgement = native_note == "acknowledged"
            notes.append(f"native_safety:{native_note}")

        if command.name in POINTER_ACTIONS and {"x", "y"} <= command.arguments.keys():
            dom_target = await hands.resolve_dom_at_normalized(
                int(command.arguments["x"]),
                int(command.arguments["y"]),
            )
            if dom_target and self._contains_high_risk_keyword(dom_target.searchable_text):
                approved = await self.approval_provider.request_approval(
                    reason="High-risk DOM target requires human approval",
                    command=command,
                    dom_target=dom_target,
                    safety_decision=command.safety_decision,
                )
                if not approved:
                    raise SafetyBlockedError("Human denied high-risk DOM action")
                safety_acknowledgement = True
                notes.append("dom_high_risk:acknowledged")

        if command.name in {"type", "type_text_at"} and "text" in command.arguments:
            if await self._is_customs_context(hands):
                clean_text = self.sanitize_hs_code(str(command.arguments["text"]))
                if clean_text != command.arguments["text"]:
                    notes.append(f"hs_code_sanitized:{command.arguments['text']!r}->{clean_text!r}")
                sanitized_command = command.with_arguments(text=clean_text)

        return GateDecision(
            command=sanitized_command,
            approved=True,
            safety_acknowledgement=safety_acknowledgement,
            dom_target=dom_target,
            notes=notes,
        )

    async def _check_native_safety(self, command: ActionCommand) -> str:
        decision = command.safety_decision or {}
        normalized = str(decision.get("decision", "")).strip().lower()
        if normalized == "blocked":
            explanation = decision.get("explanation") or "Gemini native safety blocked the action"
            raise SafetyBlockedError(str(explanation))
        if normalized == "require_confirmation":
            approved = await self.approval_provider.request_approval(
                reason=decision.get("explanation") or "Gemini requested user confirmation",
                command=command,
                safety_decision=decision,
            )
            if not approved:
                raise SafetyBlockedError("Human denied Gemini safety confirmation")
            return "acknowledged"
        return normalized or "regular"

    def _contains_high_risk_keyword(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in self.high_risk_keywords)

    async def _is_customs_context(self, hands: object) -> bool:
        url = str(getattr(hands, "url", "")).lower()
        if any(marker in url for marker in ("customs", "ics2", "declaration")):
            return True
        page_text = ""
        if hasattr(hands, "visible_text"):
            page_text = (await hands.visible_text()).lower()
        return any(marker in page_text for marker in ("customs", "ics2", "declaration"))

    @staticmethod
    def sanitize_hs_code(text: str) -> str:
        stripped = text.strip()
        if HS_CODE_RE.fullmatch(stripped):
            return stripped

        matches = HS_CODE_FIND_RE.findall(text)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SafetyBlockedError(f"Ambiguous HS codes in typed text: {matches}")

        digits = re.sub(r"\D", "", text)
        if len(digits) == 8:
            return f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"

        raise SafetyBlockedError(
            "Customs Portal typing must contain exactly one HS code matching dddd.dd.dd"
        )

