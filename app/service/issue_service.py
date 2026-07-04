from app.service.models.issue import Issue, IssueStatus, IssueType
from app.service.repositories import IssueRepository


class IssueService:
    def __init__(self, repository: IssueRepository) -> None:
        self.repository = repository

    def create_issue(
        self,
        *,
        detection: str,
        issue_type: IssueType,
        status: IssueStatus = IssueStatus.OPEN,
        embedding: list[float] | None = None,
    ) -> Issue:
        return self.repository.add(
            Issue(
                detection=detection,
                issue_type=issue_type,
                status=status,
                embedding=embedding,
            )
        )

    def get_issue(self, issue_id: int) -> Issue | None:
        return self.repository.get_by_id(issue_id)

    def list_issues(self) -> list[Issue]:
        return self.repository.list()

    def update_issue_status(self, issue_id: int, status: IssueStatus) -> Issue | None:
        return self.repository.update_status(issue_id, status)
