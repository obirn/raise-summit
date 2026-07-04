from datetime import date

from pydantic import BaseModel, ConfigDict

from app.service.models.issue import IssueStatus, IssueType


class IssueCreate(BaseModel):
    detection: str
    issue_type: IssueType
    status: IssueStatus = IssueStatus.OPEN
    embedding: list[float] | None = None


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    detection: str
    issue_type: IssueType
    status: IssueStatus
    embedding: list[float] | None
    created_at: date
    updated_at: date
