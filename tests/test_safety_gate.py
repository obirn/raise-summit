from __future__ import annotations

import pytest

from docklock.safety_gate import (
    AutoApprovalProvider,
    NetworkBoundaryException,
    SafetyBlockedError,
    SafetyGate,
    SecurityViolationException,
)
from docklock.schemas import ActionCommand, DomTarget


class FakeHands:
    def __init__(
        self,
        *,
        url: str = "http://localhost:3000/customs",
        text: str = "Customs ICS2",
        target: DomTarget | None = None,
        invoice_items: list[dict] | None = None,
    ) -> None:
        self.url = url
        self._text = text
        self._target = target or DomTarget(
            tag="button",
            text="Pay Outstanding Detention & Release Cargo",
            attributes={"role": "button"},
            x=500,
            y=500,
        )
        self._invoice_items = invoice_items or []

    async def visible_text(self) -> str:
        return self._text

    async def resolve_dom_at_normalized(self, x: int, y: int) -> DomTarget:
        return DomTarget(
            tag=self._target.tag,
            text=self._target.text,
            attributes=self._target.attributes,
            x=x,
            y=y,
        )

    async def extract_invoice_line_items(self) -> list[dict]:
        return self._invoice_items

    def is_allowed_url(self, url: str) -> bool:
        return url.startswith("http://localhost:3000")


class CapturingApprovalProvider:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved
        self.alerts = []

    async def request_approval(self, **kwargs) -> bool:
        if kwargs.get("alert"):
            self.alerts.append(kwargs["alert"].to_dict())
        return self.approved


def test_sanitize_hs_code_exact() -> None:
    assert SafetyGate.sanitize_hs_code("8517.13.00") == "8517.13.00"


def test_sanitize_hs_code_extracts_from_sentence() -> None:
    assert SafetyGate.sanitize_hs_code("The code is 8517.13.00") == "8517.13.00"


def test_sanitize_hs_code_normalizes_digits() -> None:
    assert SafetyGate.sanitize_hs_code("85171300") == "8517.13.00"


def test_sanitize_hs_code_rejects_ambiguous_text() -> None:
    with pytest.raises(SafetyBlockedError):
        SafetyGate.sanitize_hs_code("Use 8517.13.00 or 8517.12.00")


async def test_type_action_is_sanitized_in_customs_context() -> None:
    gate = SafetyGate(AutoApprovalProvider())
    decision = await gate.validate(
        ActionCommand(name="type", arguments={"text": "The corrected HS is 8517.13.00"}),
        FakeHands(),
    )
    assert decision.command.arguments["text"] == "8517.13.00"


async def test_high_risk_dom_click_requires_acknowledgement() -> None:
    target = DomTarget(tag="button", text="Validate & Re-submit", attributes={"role": "button"}, x=500, y=500)
    gate = SafetyGate(AutoApprovalProvider())
    decision = await gate.validate(
        ActionCommand(name="click", arguments={"x": 500, "y": 500}),
        FakeHands(target=target),
    )
    assert decision.safety_acknowledgement is True


async def test_native_block_raises_security_violation() -> None:
    gate = SafetyGate(AutoApprovalProvider())
    with pytest.raises(SecurityViolationException, match="content filters"):
        await gate.validate(
            ActionCommand(name="click", arguments={"safety_decision": "blocked"}),
            FakeHands(),
        )


async def test_native_confirmation_builds_hitl_alert_and_acknowledgement() -> None:
    provider = CapturingApprovalProvider()
    gate = SafetyGate(provider)
    decision = await gate.validate(
        ActionCommand(
            name="click",
            arguments={
                "x": 520,
                "y": 410,
                "safety_decision": {"decision": "require_confirmation", "explanation": "Submit action"},
            },
        ),
        FakeHands(target=DomTarget(tag="button", text="Continue", attributes={}, x=520, y=410)),
    )
    assert decision.safety_acknowledgement is True
    assert provider.alerts[0]["status"] == "PAUSED_FOR_HITL"
    assert provider.alerts[0]["intercept_reason"] == "NATIVE_AI_CONFIRMATION_REQUIRED"
    assert provider.alerts[0]["gemini_proposal"]["native_safety_decision"] == "require_confirmation"


async def test_unapproved_hs_code_pauses_for_hitl_and_blocks_when_denied() -> None:
    provider = CapturingApprovalProvider(approved=False)
    gate = SafetyGate(provider)
    with pytest.raises(SafetyBlockedError, match="not recognized"):
        await gate.validate(
            ActionCommand(name="type", arguments={"text": "9999.99.99"}),
            FakeHands(),
        )
    assert provider.alerts[0]["intercept_reason"] == "UNRECOGNIZED_TARIFF_CODE"
    assert provider.alerts[0]["container_id"] == "MSKU4471"


async def test_physical_weight_manifest_edit_is_permanently_blocked() -> None:
    gate = SafetyGate(AutoApprovalProvider())
    target = DomTarget(
        tag="button",
        text="Edit vgmWeight",
        attributes={"data-field": "vgmWeight"},
        x=300,
        y=200,
    )
    with pytest.raises(SecurityViolationException, match="physical weight manifests"):
        await gate.validate(
            ActionCommand(name="click", arguments={"x": 300, "y": 200}),
            FakeHands(
                url="http://localhost:3000/tms",
                text="Legacy TMS vgmWeight 22,400 KG Carrier scale 23,100 KG discrepancy +700 KG",
                target=target,
            ),
        )


async def test_unbudgeted_terminal_fee_builds_exact_hitl_schema() -> None:
    provider = CapturingApprovalProvider()
    gate = SafetyGate(provider)
    target = DomTarget(
        tag="button",
        text="[ Pay Total Balance: $465.00 ]",
        attributes={"role": "button"},
        x=520,
        y=410,
    )
    decision = await gate.validate(
        ActionCommand(name="click", arguments={"x": 520, "y": 410}),
        FakeHands(
            url="http://localhost:3000/terminal",
            text="Hyper-Local Terminal Gate",
            target=target,
            invoice_items=[
                {"label": "Detention Fee", "amount": 340.00},
                {"label": "X-Ray Inspection Fee", "amount": 125.00},
                {"label": "Total Balance", "amount": 465.00},
            ],
        ),
    )
    alert = provider.alerts[0]
    assert decision.safety_acknowledgement is True
    assert alert["status"] == "PAUSED_FOR_HITL"
    assert alert["intercept_reason"] == "UNBUDGETED_FEE_DETECTED"
    assert alert["gemini_proposal"]["coordinates"] == {"x": 520, "y": 410}
    assert alert["dom_resolution"]["element_tag"] == "BUTTON"
    assert alert["dom_resolution"]["target_portal"] == "Hyper-Local Terminal Gate"
    assert "$125.00 (X-Ray Inspection Fee)" in alert["business_context"]
    assert alert["required_action"] == "1-TAP_HUMAN_APPROVAL"


async def test_safety_gate_blocks_external_navigation() -> None:
    gate = SafetyGate(AutoApprovalProvider())
    with pytest.raises(NetworkBoundaryException):
        await gate.validate(
            ActionCommand(name="navigate", arguments={"url": "https://google.com"}),
            FakeHands(),
        )
