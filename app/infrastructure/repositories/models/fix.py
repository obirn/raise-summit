from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.service.models.fix import FixResult


class FixCreate(BaseModel):
    issue_id: int
    action_details: str
    result: FixResult | None = None
    execution_log: dict[str, Any] | None = None
    human_input: str | None = None


class FixRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    action_details: str
    result: FixResult | None
    execution_log: dict[str, Any] | None
    human_input: str | None
    created_at: date
    updated_at: date
