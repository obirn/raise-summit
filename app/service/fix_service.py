from app.service.models.fix import Fix, FixResult
from app.service.repositories import FixRepository, IssueRepository


class IssueNotFoundError(ValueError):
    pass


class FixService:
    def __init__(self, fix_repository: FixRepository, issue_repository: IssueRepository) -> None:
        self.fix_repository = fix_repository
        self.issue_repository = issue_repository

    def create_fix(
        self,
        *,
        issue_id: int,
        action_details: str,
        result: FixResult | None = None,
        execution_log: dict | None = None,
        human_input: str | None = None,
    ) -> Fix:
        if self.issue_repository.get_by_id(issue_id) is None:
            raise IssueNotFoundError(f"Issue with id {issue_id} does not exist")

        return self.fix_repository.add(
            Fix(
                issue_id=issue_id,
                action_details=action_details,
                result=result,
                execution_log=execution_log,
                human_input=human_input,
            )
        )

    def get_fix(self, fix_id: int) -> Fix | None:
        return self.fix_repository.get_by_id(fix_id)

    def list_fixes_for_issue(self, issue_id: int) -> list[Fix]:
        return self.fix_repository.list_by_issue_id(issue_id)

    def list_successful_fixes(self) -> list[Fix]:
        return self.fix_repository.list_successful()
