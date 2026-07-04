from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from .schemas import ActionCommand, DomTarget, GateDecision, HitlAlert


HS_CODE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
HS_CODE_FIND_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}")
MONEY_RE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")

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


class SecurityViolationException(SafetyBlockedError):
    """Raised when native AI safety or deterministic policy terminates an action."""


class NetworkBoundaryException(SafetyBlockedError):
    """Raised when the model attempts to leave the browser allowlist."""


class ApprovalProvider(Protocol):
    async def request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
        alert: HitlAlert | None = None,
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
        alert: HitlAlert | None = None,
    ) -> bool:
        print("\n[HITL] Human approval required")
        print(f"[HITL] Reason: {reason}")
        if alert:
            print("[HITL] Alert payload:")
            print(json.dumps(alert.to_dict(), indent=2))
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
        alert: HitlAlert | None = None,
    ) -> bool:
        target = f" target=<{dom_target.tag}> {dom_target.text!r}" if dom_target else ""
        if alert:
            print(f"[HITL:auto-approved] {json.dumps(alert.to_dict())}")
        else:
            print(f"[HITL:auto-approved] {reason}; action={command.name}{target}")
        return True


@dataclass
class WebSocketApprovalProvider:
    """Push HITL alerts to a dashboard WebSocket and wait for a one-tap response."""

    url: str
    timeout_seconds: float = 120.0

    async def request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
        alert: HitlAlert | None = None,
    ) -> bool:
        import websockets

        payload = {
            "type": "docklock.hitl.request",
            "reason": reason,
            "alert": alert.to_dict() if alert else None,
            "command": {"name": command.name, "arguments": command.arguments},
            "safety_decision": safety_decision,
        }
        async with websockets.connect(self.url) as socket:
            await socket.send(json.dumps(payload))
            async with asyncio.timeout(self.timeout_seconds):
                response = json.loads(await socket.recv())
        return bool(response.get("approved"))


class SafetyGate:
    def __init__(
        self,
        approval_provider: ApprovalProvider,
        high_risk_keywords: tuple[str, ...] | None = None,
        *,
        container_id: str = "MSKU4471",
        approved_hs_codes: tuple[str, ...] = ("8517.13.00",),
        authorized_po_ledger: dict[str, float] | None = None,
        allowed_origins: tuple[str, ...] = ("http://localhost:3000",),
    ) -> None:
        self.approval_provider = approval_provider
        self.container_id = container_id
        self.approved_hs_codes = set(approved_hs_codes)
        self.authorized_po_ledger = authorized_po_ledger or {"detention": 340.00}
        self.allowed_origins = set(allowed_origins)
        self.high_risk_keywords = high_risk_keywords or (
            "pay",
            "payment",
            "submit",
            "validate & re-submit",
            "validate and re-submit",
            "delete",
            "override",
            "confirm",
            "release cargo",
        )
        self.immutable_fields = ("vgmweight", "vgm weight", "sealnumber", "seal number", "containerid", "container id")
        self.physical_edit_triggers = ("edit", "update", "override", "save")

    async def validate(self, command: ActionCommand, hands: object) -> GateDecision:
        notes: list[str] = []
        safety_acknowledgement = False
        dom_target: DomTarget | None = None
        sanitized_command = command
        payment_handled = False

        if command.safety_decision:
            native_note = await self._check_native_safety(command)
            safety_acknowledgement = native_note == "acknowledged"
            notes.append(f"native_safety:{native_note}")

        if command.name == "navigate":
            self._check_navigation_boundary(str(command.arguments.get("url", "")), hands)

        if command.name in POINTER_ACTIONS and {"x", "y"} <= command.arguments.keys():
            dom_target = await hands.resolve_dom_at_normalized(
                int(command.arguments["x"]),
                int(command.arguments["y"]),
            )
            page_text = await self._safe_visible_text(hands)
            target_portal = self._target_portal(hands, page_text)
            if dom_target and self._is_physical_manifest_override(dom_target, page_text):
                message = (
                    "Physical measurement discrepancy detected (+700 KG). "
                    "AI is prohibited from overriding physical weight manifests."
                )
                raise SecurityViolationException(message)

            if dom_target and self._is_payment_target(dom_target):
                approved = await self._handle_payment_intercept(
                    command,
                    hands,
                    dom_target=dom_target,
                    target_portal=target_portal,
                )
                if not approved:
                    raise SafetyBlockedError("Human denied unbudgeted payment action")
                safety_acknowledgement = True
                notes.append("unbudgeted_fee:acknowledged")
                payment_handled = True

            if (
                dom_target
                and not payment_handled
                and self._contains_high_risk_keyword(dom_target.searchable_text)
            ):
                alert = self._build_alert(
                    intercept_reason="HIGH_RISK_DOM_ACTION",
                    command=command,
                    dom_target=dom_target,
                    target_portal=target_portal,
                    business_context="Target text or attributes match irreversible action keywords.",
                )
                approved = await self._request_approval(
                    reason="High-risk DOM target requires human approval",
                    command=command,
                    dom_target=dom_target,
                    alert=alert,
                )
                if not approved:
                    raise SafetyBlockedError("Human denied high-risk DOM action")
                safety_acknowledgement = True
                notes.append("dom_high_risk:acknowledged")

        if command.name in {"type", "type_text_at"} and "text" in command.arguments:
            if {"x", "y"} <= command.arguments.keys():
                dom_target = await hands.resolve_dom_at_normalized(
                    int(command.arguments["x"]),
                    int(command.arguments["y"]),
                )
                if dom_target and self._target_mentions_immutable_field(dom_target):
                    raise SecurityViolationException(
                        "AI is prohibited from editing immutable physical container fields."
                    )
            if await self._is_customs_context(hands):
                clean_text = await self._validate_customs_hs_code(command, hands, dom_target)
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
            print("Action terminated by native AI content filters.")
            explanation = decision.get("explanation") or "Action terminated by native AI content filters."
            raise SecurityViolationException(str(explanation))
        if normalized == "require_confirmation":
            alert = self._build_alert(
                intercept_reason="NATIVE_AI_CONFIRMATION_REQUIRED",
                command=command,
                business_context=decision.get("explanation") or "Gemini requested user confirmation.",
                native_safety_decision=normalized,
            )
            approved = await self._request_approval(
                reason=decision.get("explanation") or "Gemini requested user confirmation",
                command=command,
                safety_decision=decision,
                alert=alert,
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

    async def _validate_customs_hs_code(
        self,
        command: ActionCommand,
        hands: object,
        dom_target: DomTarget | None,
    ) -> str:
        raw_text = str(command.arguments["text"])
        clean_text = self.sanitize_hs_code(raw_text)
        if clean_text in self.approved_hs_codes:
            return clean_text

        alert = self._build_alert(
            intercept_reason="UNRECOGNIZED_TARIFF_CODE",
            command=command,
            dom_target=dom_target,
            target_portal=self._target_portal(hands, await self._safe_visible_text(hands)),
            business_context=(
                f"Tariff code {clean_text} is not recognized in our standard catalog. "
                "Please manually verify classification."
            ),
        )
        approved = await self._request_approval(
            reason=alert.business_context,
            command=command,
            dom_target=dom_target,
            alert=alert,
        )
        if not approved:
            raise SafetyBlockedError(
                f"Tariff code {clean_text} is not recognized in our standard catalog. "
                "Please manually verify classification."
            )
        return clean_text

    async def _handle_payment_intercept(
        self,
        command: ActionCommand,
        hands: object,
        *,
        dom_target: DomTarget,
        target_portal: str,
    ) -> bool:
        line_items = await self._extract_invoice_line_items(hands)
        unauthorized = self._find_unauthorized_invoice_items(line_items)
        if unauthorized:
            context = "; ".join(
                f"${item['amount']:.2f} ({item['label'] or 'Unlabeled fee'})" for item in unauthorized
            )
            alert = self._build_alert(
                intercept_reason="UNBUDGETED_FEE_DETECTED",
                command=command,
                dom_target=dom_target,
                target_portal=target_portal,
                business_context=(
                    f"Unbudgeted line item detected: {context}. "
                    "No matching PO found. Do you authorize this expense?"
                ),
            )
            return await self._request_approval(
                reason=alert.business_context,
                command=command,
                dom_target=dom_target,
                alert=alert,
            )

        alert = self._build_alert(
            intercept_reason="PAYMENT_ACTION_REQUIRES_APPROVAL",
            command=command,
            dom_target=dom_target,
            target_portal=target_portal,
            business_context="Payment action matched authorized PO ledger but still requires human approval.",
        )
        return await self._request_approval(
            reason=alert.business_context,
            command=command,
            dom_target=dom_target,
            alert=alert,
        )

    async def _extract_invoice_line_items(self, hands: object) -> list[dict[str, float | str]]:
        if hasattr(hands, "extract_invoice_line_items"):
            raw_items = await hands.extract_invoice_line_items()
        else:
            raw_items = self._extract_invoice_line_items_from_text(await self._safe_visible_text(hands))

        items: list[dict[str, float | str]] = []
        for item in raw_items:
            label = str(item.get("label", ""))
            amount = item.get("amount")
            if amount is None and "amount_text" in item:
                amount = self._money_to_float(str(item["amount_text"]))
            if amount is None:
                continue
            items.append({"label": label, "amount": float(amount)})
        return items

    def _extract_invoice_line_items_from_text(self, text: str) -> list[dict[str, float | str]]:
        items: list[dict[str, float | str]] = []
        for line in text.splitlines():
            for amount_text in MONEY_RE.findall(line):
                amount = self._money_to_float(amount_text)
                label = MONEY_RE.sub("", line).strip(" :-|")
                items.append({"label": label, "amount": amount})
        return items

    def _find_unauthorized_invoice_items(
        self,
        line_items: list[dict[str, float | str]],
    ) -> list[dict[str, float | str]]:
        unauthorized: list[dict[str, float | str]] = []
        for item in line_items:
            label = str(item.get("label", "")).lower()
            amount = float(item["amount"])
            if any(summary in label for summary in ("total", "balance")) and len(line_items) > 1:
                continue
            matched = False
            for authorized_label, authorized_amount in self.authorized_po_ledger.items():
                if authorized_label.lower() in label and amount <= authorized_amount:
                    matched = True
                    break
            if not matched:
                unauthorized.append(item)
        return unauthorized

    def _is_payment_target(self, dom_target: DomTarget) -> bool:
        target_text = dom_target.searchable_text
        return any(marker in target_text for marker in ("pay", "payment", "balance", "fee"))

    def _is_physical_manifest_override(self, dom_target: DomTarget, page_text: str) -> bool:
        target_text = dom_target.searchable_text
        has_edit_trigger = any(trigger in target_text for trigger in self.physical_edit_triggers)
        physical_context = self._target_mentions_immutable_field(dom_target) or any(
            field in page_text.lower() for field in self.immutable_fields
        )
        discrepancy_context = any(
            marker in page_text.lower()
            for marker in ("22,400 kg", "22400 kg", "23,100 kg", "23100 kg", "+700 kg", "discrepancy")
        )
        return has_edit_trigger and physical_context and discrepancy_context

    def _target_mentions_immutable_field(self, dom_target: DomTarget) -> bool:
        target_text = dom_target.searchable_text.replace("_", "").replace("-", "")
        return any(field.replace(" ", "") in target_text for field in self.immutable_fields)

    async def _safe_visible_text(self, hands: object) -> str:
        if hasattr(hands, "visible_text"):
            return await hands.visible_text()
        return ""

    def _target_portal(self, hands: object, page_text: str) -> str:
        probe = f"{getattr(hands, 'url', '')} {page_text}".lower()
        if "terminal" in probe or "gate" in probe:
            return "Hyper-Local Terminal Gate"
        if "customs" in probe or "ics2" in probe or "declaration" in probe:
            return "Customs ICS2"
        if "carrier" in probe:
            return "Carrier Portal"
        if "tms" in probe or "manifest" in probe:
            return "Legacy TMS"
        return "Unknown Portal"

    def _build_alert(
        self,
        *,
        intercept_reason: str,
        command: ActionCommand,
        business_context: str,
        dom_target: DomTarget | None = None,
        target_portal: str = "Unknown Portal",
        native_safety_decision: str | None = None,
    ) -> HitlAlert:
        native_decision = native_safety_decision or self._native_safety_decision_text(command)
        return HitlAlert.build(
            container_id=self.container_id,
            intercept_reason=intercept_reason,
            command=command,
            dom_target=dom_target,
            target_portal=target_portal,
            business_context=business_context,
            native_safety_decision=native_decision,
        )

    async def _request_approval(
        self,
        *,
        reason: str,
        command: ActionCommand,
        dom_target: DomTarget | None = None,
        safety_decision: dict | None = None,
        alert: HitlAlert | None = None,
    ) -> bool:
        return await self.approval_provider.request_approval(
            reason=reason,
            command=command,
            dom_target=dom_target,
            safety_decision=safety_decision,
            alert=alert,
        )

    def _native_safety_decision_text(self, command: ActionCommand) -> str:
        decision = command.safety_decision or {}
        return str(decision.get("decision", "regular"))

    def _check_navigation_boundary(self, url: str, hands: object) -> None:
        if hasattr(hands, "is_allowed_url") and hands.is_allowed_url(url):
            return
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.allowed_origins:
            raise NetworkBoundaryException(f"Navigation outside allowlist blocked by Safety Gate: {url}")

    @staticmethod
    def _money_to_float(amount_text: str) -> float:
        return float(str(amount_text).replace("$", "").replace(",", "").strip())

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
