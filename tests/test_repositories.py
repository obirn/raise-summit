import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.repositories.fix_repository import SqlAlchemyFixRepository
from app.infrastructure.repositories.issue_repository import SqlAlchemyIssueRepository
from app.infrastructure.tables.base import Base
from app.service.models.fix import Fix, FixResult
from app.service.models.issue import Issue, IssueStatus, IssueType


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.issue_repository = SqlAlchemyIssueRepository(self.session)
        self.fix_repository = SqlAlchemyFixRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_issue_repository_add_get_list_and_update_status(self) -> None:
        issue = self.issue_repository.add(
            Issue(
                detection="State mismatch detected for ID 1002",
                issue_type=IssueType.SYSTEM_DIFFERENCE,
                embedding=[0.1, 0.2, 0.3],
            )
        )

        self.assertIsNotNone(issue.id)
        self.assertEqual(issue.status, IssueStatus.OPEN)
        self.assertEqual(issue.embedding, [0.1, 0.2, 0.3])

        fetched = self.issue_repository.get_by_id(issue.id)
        self.assertEqual(fetched, issue)
        self.assertEqual(self.issue_repository.list(), [issue])

        updated = self.issue_repository.update_status(issue.id, IssueStatus.AUTO_RESOLVED)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, IssueStatus.AUTO_RESOLVED)
        self.assertEqual(
            self.issue_repository.get_by_id(issue.id).status,
            IssueStatus.AUTO_RESOLVED,
        )

    def test_issue_repository_returns_none_for_missing_rows(self) -> None:
        self.assertIsNone(self.issue_repository.get_by_id(404))
        self.assertIsNone(self.issue_repository.update_status(404, IssueStatus.FAILED))

    def test_fix_repository_add_get_and_list_by_issue_id(self) -> None:
        issue = self.issue_repository.add(
            Issue(
                detection="State mismatch detected for ID 1002",
                issue_type=IssueType.SYSTEM_DIFFERENCE,
            )
        )
        other_issue = self.issue_repository.add(
            Issue(
                detection="Customer reported call issue",
                issue_type=IssueType.CALL_COMPLAINT,
            )
        )

        fix = self.fix_repository.add(
            Fix(
                issue_id=issue.id,
                action_details="Update App 2 to PENDING",
                result=FixResult.SUCCESS,
                execution_log={"steps": ["open app", "save state"]},
                human_input="Use the majority state",
            )
        )
        other_fix = self.fix_repository.add(
            Fix(
                issue_id=other_issue.id,
                action_details="Escalate to support",
                result=FixResult.UNKNOWN,
            )
        )

        self.assertIsNotNone(fix.id)
        self.assertEqual(self.fix_repository.get_by_id(fix.id), fix)
        self.assertEqual(self.fix_repository.list_by_issue_id(issue.id), [fix])
        self.assertEqual(self.fix_repository.list_by_issue_id(other_issue.id), [other_fix])

    def test_fix_repository_lists_only_successful_fixes(self) -> None:
        issue = self.issue_repository.add(
            Issue(
                detection="State mismatch detected for ID 1002",
                issue_type=IssueType.SYSTEM_DIFFERENCE,
            )
        )
        successful_fix = self.fix_repository.add(
            Fix(
                issue_id=issue.id,
                action_details="Update App 2 to PENDING",
                result=FixResult.SUCCESS,
            )
        )
        self.fix_repository.add(
            Fix(
                issue_id=issue.id,
                action_details="Tried updating App 2",
                result=FixResult.FAILED,
            )
        )

        self.assertEqual(self.fix_repository.list_successful(), [successful_fix])

    def test_fix_repository_returns_none_for_missing_rows(self) -> None:
        self.assertIsNone(self.fix_repository.get_by_id(404))


if __name__ == "__main__":
    unittest.main()
