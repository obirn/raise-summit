from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any


class FixResult(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class Fix:
    issue_id: int
    action_details: str
    result: FixResult | None = None
    execution_log: dict[str, Any] | None = None
    human_input: str | None = None
    created_at: date | None = None
    updated_at: date | None = None
    id: int | None = None
