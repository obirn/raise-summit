from typing import Protocol

from app.service.models.fix import Fix
from app.service.models.issue import Issue, IssueStatus


class IssueRepository(Protocol):
    def add(self, issue: Issue) -> Issue:
        raise NotImplementedError

    def get_by_id(self, issue_id: int) -> Issue | None:
        raise NotImplementedError

    def list(self) -> list[Issue]:
        raise NotImplementedError

    def update_status(self, issue_id: int, status: IssueStatus) -> Issue | None:
        raise NotImplementedError


class FixRepository(Protocol):
    def add(self, fix: Fix) -> Fix:
        raise NotImplementedError

    def get_by_id(self, fix_id: int) -> Fix | None:
        raise NotImplementedError

    def list_by_issue_id(self, issue_id: int) -> list[Fix]:
        raise NotImplementedError

    def list_successful(self) -> list[Fix]:
        raise NotImplementedError
