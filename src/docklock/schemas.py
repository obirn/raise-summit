from __future__ import annotations

from dataclasses import dataclass, field, replace
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
        return decision if isinstance(decision, dict) else None

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

