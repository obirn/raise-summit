from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class ActionCommand:
    """A normalized UI action proposed by the model."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None

    @property
    def intent(self) -> str:
        return str(self.arguments.get("intent", ""))

    @property
    def safety_decision(self) -> dict[str, Any] | None:
        decision = self.arguments.get("safety_decision")
        if isinstance(decision, dict):
            return decision
        if isinstance(decision, str):
            return {"decision": decision}
        return None

    def with_arguments(self, **updates: Any) -> "ActionCommand":
        args = dict(self.arguments)
        args.update(updates)
        return replace(self, arguments=args)


@dataclass(frozen=True)
class DomTarget:
    tag: str
    text: str
    attributes: dict[str, str]
    x: int
    y: int

    @property
    def searchable_text(self) -> str:
        attrs = " ".join(f"{key}={value}" for key, value in self.attributes.items())
        return f"{self.tag} {self.text} {attrs}".lower()


@dataclass(frozen=True)
class GateDecision:
    command: ActionCommand
    approved: bool
    safety_acknowledgement: bool = False
    dom_target: DomTarget | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HitlAlert:
    status: str
    timestamp: str
    container_id: str
    intercept_reason: str
    gemini_proposal: dict[str, Any]
    dom_resolution: dict[str, Any]
    business_context: str
    required_action: str = "1-TAP_HUMAN_APPROVAL"

    @classmethod
    def build(
        cls,
        *,
        container_id: str,
        intercept_reason: str,
        command: ActionCommand,
        business_context: str,
        dom_target: DomTarget | None = None,
        target_portal: str = "Unknown Portal",
        native_safety_decision: str = "regular",
    ) -> "HitlAlert":
        coordinates: dict[str, int] = {}
        if "x" in command.arguments and "y" in command.arguments:
            coordinates = {"x": int(command.arguments["x"]), "y": int(command.arguments["y"])}

        return cls(
            status="PAUSED_FOR_HITL",
            timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            container_id=container_id,
            intercept_reason=intercept_reason,
            gemini_proposal={
                "action": command.name,
                "coordinates": coordinates,
                "native_safety_decision": native_safety_decision,
            },
            dom_resolution={
                "element_tag": dom_target.tag.upper() if dom_target else "",
                "element_text": dom_target.text if dom_target else "",
                "target_portal": target_portal,
            },
            business_context=business_context,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "container_id": self.container_id,
            "intercept_reason": self.intercept_reason,
            "gemini_proposal": self.gemini_proposal,
            "dom_resolution": self.dom_resolution,
            "business_context": self.business_context,
            "required_action": self.required_action,
        }


@dataclass(frozen=True)
class ActionResult:
    name: str
    call_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)


def _get_field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return dict(value)


def iter_function_calls(interaction: Any) -> Iterable[ActionCommand]:
    """Yield function calls from google-genai interaction objects or dict fixtures."""

    steps = _get_field(interaction, "steps", []) or []
    for step in steps:
        if _get_field(step, "type") != "function_call":
            continue
        yield ActionCommand(
            name=str(_get_field(step, "name")),
            arguments=_as_dict(_get_field(step, "arguments", {})),
            call_id=_get_field(step, "id") or _get_field(step, "call_id"),
        )


def collect_model_text(interaction: Any) -> str:
    chunks: list[str] = []
    steps = _get_field(interaction, "steps", []) or []
    for step in steps:
        if _get_field(step, "type") != "model_output":
            continue
        for block in _get_field(step, "content", []) or []:
            if _get_field(block, "type") == "text":
                chunks.append(str(_get_field(block, "text", "")))
    return " ".join(chunk for chunk in chunks if chunk).strip()
