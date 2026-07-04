from __future__ import annotations

import pytest

from docklock.safety_gate import AutoApprovalProvider, SafetyBlockedError, SafetyGate
from docklock.schemas import ActionCommand, DomTarget


class FakeHands:
    def __init__(self, *, url: str = "http://localhost:3000/customs", text: str = "Customs ICS2") -> None:
        self.url = url
        self._text = text

    async def visible_text(self) -> str:
        return self._text

    async def resolve_dom_at_normalized(self, x: int, y: int) -> DomTarget:
        return DomTarget(
            tag="button",
            text="Pay Outstanding Detention & Release Cargo",
            attributes={"role": "button"},
            x=x,
            y=y,
        )


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
    gate = SafetyGate(AutoApprovalProvider())
    decision = await gate.validate(
        ActionCommand(name="click", arguments={"x": 500, "y": 500}),
        FakeHands(),
    )
    assert decision.safety_acknowledgement is True

