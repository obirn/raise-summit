from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.tables.fix_table import FixTable
from app.service.models.fix import Fix, FixResult
from app.service.repositories import FixRepository


class SqlAlchemyFixRepository(FixRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, fix: Fix) -> Fix:
        row = FixTable(
            issue_id=fix.issue_id,
            action_details=fix.action_details,
            result=fix.result,
            execution_log=fix.execution_log,
            human_input=fix.human_input,
        )
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    def get_by_id(self, fix_id: int) -> Fix | None:
        row = self.session.get(FixTable, fix_id)
        if row is None:
            return None
        return self._to_domain(row)

    def list_by_issue_id(self, issue_id: int) -> list[Fix]:
        rows = self.session.scalars(
            select(FixTable).where(FixTable.issue_id == issue_id).order_by(FixTable.id)
        ).all()
        return [self._to_domain(row) for row in rows]

    def list_successful(self) -> list[Fix]:
        rows = self.session.scalars(
            select(FixTable).where(FixTable.result == FixResult.SUCCESS).order_by(FixTable.id)
        ).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: FixTable) -> Fix:
        return Fix(
            id=row.id,
            issue_id=row.issue_id,
            action_details=row.action_details,
            result=row.result,
            execution_log=row.execution_log,
            human_input=row.human_input,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
