import unittest
from datetime import date

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.infrastructure.tables.base import Base
from app.infrastructure.tables.container_table import ContainerTable
from app.infrastructure.tables.fix_table import FixTable
from app.infrastructure.tables.issue_table import IssueTable
from app.service.models.fix import FixResult
from app.service.models.issue import IssueStatus, IssueType


class TableMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_issue_table_schema_contains_expected_columns(self) -> None:
        columns = inspect(self.engine).get_columns("issues")
        column_names = {column["name"] for column in columns}

        self.assertEqual(
            column_names,
            {
                "id",
                "detection",
                "issue_type",
                "status",
                "embedding",
                "created_at",
                "updated_at",
            },
        )

        nullable_by_name = {column["name"]: column["nullable"] for column in columns}
        self.assertFalse(nullable_by_name["detection"])
        self.assertFalse(nullable_by_name["issue_type"])
        self.assertTrue(nullable_by_name["embedding"])

    def test_container_table_schema_contains_expected_columns(self) -> None:
        columns = inspect(self.engine).get_columns("containers")
        column_names = {column["name"] for column in columns}

        self.assertEqual(column_names, {"id", "conflict"})

        nullable_by_name = {column["name"]: column["nullable"] for column in columns}
        self.assertFalse(nullable_by_name["conflict"])

    def test_fix_table_schema_contains_expected_columns_and_foreign_key(self) -> None:
        columns = inspect(self.engine).get_columns("fixes")
        column_names = {column["name"] for column in columns}

        self.assertEqual(
            column_names,
            {
                "id",
                "issue_id",
                "action_details",
                "result",
                "execution_log",
                "human_input",
                "created_at",
                "updated_at",
            },
        )

        foreign_keys = inspect(self.engine).get_foreign_keys("fixes")
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0]["constrained_columns"], ["issue_id"])
        self.assertEqual(foreign_keys[0]["referred_table"], "issues")
        self.assertEqual(foreign_keys[0]["referred_columns"], ["id"])

        nullable_by_name = {column["name"]: column["nullable"] for column in columns}
        self.assertTrue(nullable_by_name["result"])

    def test_issue_table_defaults_are_persisted(self) -> None:
        issue = IssueTable(
            detection="State mismatch detected",
            issue_type=IssueType.SYSTEM_DIFFERENCE,
        )

        self.session.add(issue)
        self.session.flush()

        self.assertIsNotNone(issue.id)
        self.assertEqual(issue.status, IssueStatus.OPEN)
        self.assertIsNone(issue.embedding)
        self.assertIsInstance(issue.created_at, date)
        self.assertIsInstance(issue.updated_at, date)

    def test_container_table_default_conflict_is_false(self) -> None:
        container = ContainerTable()

        self.session.add(container)
        self.session.flush()

        self.assertIsNotNone(container.id)
        self.assertFalse(container.conflict)

    def test_issue_and_fix_relationship_round_trip(self) -> None:
        issue = IssueTable(
            detection="App 2 differs from the majority",
            issue_type=IssueType.SYSTEM_DIFFERENCE,
        )
        fix = FixTable(
            issue=issue,
            action_details="Update App 2 to PENDING",
            result=FixResult.SUCCESS,
        )

        self.session.add(fix)
        self.session.flush()

        self.assertEqual(fix.issue_id, issue.id)
        self.assertEqual(issue.fixes, [fix])
        self.assertEqual(fix.issue, issue)


if __name__ == "__main__":
    unittest.main()
