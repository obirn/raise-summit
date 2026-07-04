from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.tables.issue_table import IssueTable
from app.service.models.issue import Issue, IssueStatus
from app.service.repositories import IssueRepository


class SqlAlchemyIssueRepository(IssueRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, issue: Issue) -> Issue:
        row = IssueTable(
            detection=issue.detection,
            issue_type=issue.issue_type,
            status=issue.status,
            embedding=issue.embedding,
        )
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    def get_by_id(self, issue_id: int) -> Issue | None:
        row = self.session.get(IssueTable, issue_id)
        if row is None:
            return None
        return self._to_domain(row)

    def list(self) -> list[Issue]:
        rows = self.session.scalars(select(IssueTable).order_by(IssueTable.id)).all()
        return [self._to_domain(row) for row in rows]

    def update_status(self, issue_id: int, status: IssueStatus) -> Issue | None:
        row = self.session.get(IssueTable, issue_id)
        if row is None:
            return None
        row.status = status
        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: IssueTable) -> Issue:
        return Issue(
            id=row.id,
            detection=row.detection,
            issue_type=row.issue_type,
            status=row.status,
            embedding=row.embedding,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
