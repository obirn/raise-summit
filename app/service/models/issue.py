from dataclasses import dataclass
from datetime import date
from enum import Enum


class IssueType(str, Enum):
    SYSTEM_DIFFERENCE = "SYSTEM_DIFFERENCE"
    CALL_COMPLAINT = "CALL_COMPLAINT"
    ELSE = "ELSE"


class IssueStatus(str, Enum):
    OPEN = "OPEN"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


@dataclass
class Issue:
    detection: str
    issue_type: IssueType
    status: IssueStatus = IssueStatus.OPEN
    embedding: list[float] | None = None
    created_at: date | None = None
    updated_at: date | None = None
    id: int | None = None
