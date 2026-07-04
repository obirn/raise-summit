from fastapi import APIRouter, HTTPException, status

from app.infrastructure.database import SessionLocal
from app.infrastructure.repositories.fix_repository import SqlAlchemyFixRepository
from app.infrastructure.repositories.issue_repository import SqlAlchemyIssueRepository
from app.infrastructure.repositories.models.fix import FixCreate, FixRead
from app.infrastructure.repositories.models.issue import IssueCreate, IssueRead
from app.service.fix_service import FixService, IssueNotFoundError
from app.service.issue_service import IssueService


class IssueRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/issues", tags=["issues"])
        self.router.add_api_route(
            "",
            self.create_issue,
            methods=["POST"],
            response_model=IssueRead,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route("", self.list_issues, methods=["GET"], response_model=list[IssueRead])
        self.router.add_api_route("/{issue_id}", self.get_issue, methods=["GET"], response_model=IssueRead)
        self.router.add_api_route(
            "/{issue_id}/fixes",
            self.list_fixes_for_issue,
            methods=["GET"],
            response_model=list[FixRead],
        )

    def create_issue(self, payload: IssueCreate) -> IssueRead:
        session = SessionLocal()
        try:
            repository = SqlAlchemyIssueRepository(session)
            service = IssueService(repository)
            issue = service.create_issue(
                detection=payload.detection,
                issue_type=payload.issue_type,
                embedding=payload.embedding,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return IssueRead.model_validate(issue)

    def list_issues(self) -> list[IssueRead]:
        session = SessionLocal()
        try:
            repository = SqlAlchemyIssueRepository(session)
            service = IssueService(repository)
            issues = service.list_issues()
        finally:
            session.close()

        return [IssueRead.model_validate(issue) for issue in issues]

    def get_issue(self, issue_id: int) -> IssueRead:
        session = SessionLocal()
        try:
            repository = SqlAlchemyIssueRepository(session)
            service = IssueService(repository)
            issue = service.get_issue(issue_id)
        finally:
            session.close()

        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        return IssueRead.model_validate(issue)

    def list_fixes_for_issue(self, issue_id: int) -> list[FixRead]:
        session = SessionLocal()
        try:
            issue_repository = SqlAlchemyIssueRepository(session)
            issue_service = IssueService(issue_repository)
            issue = issue_service.get_issue(issue_id)
            if issue is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

            fix_repository = SqlAlchemyFixRepository(session)
            fix_service = FixService(fix_repository, issue_repository)
            fixes = fix_service.list_fixes_for_issue(issue_id)
        finally:
            session.close()

        return [FixRead.model_validate(fix) for fix in fixes]


class FixRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/fixes", tags=["fixes"])
        self.router.add_api_route(
            "",
            self.create_fix,
            methods=["POST"],
            response_model=FixRead,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route("/{fix_id}", self.get_fix, methods=["GET"], response_model=FixRead)

    def create_fix(self, payload: FixCreate) -> FixRead:
        session = SessionLocal()
        try:
            issue_repository = SqlAlchemyIssueRepository(session)
            fix_repository = SqlAlchemyFixRepository(session)
            service = FixService(fix_repository, issue_repository)
            fix = service.create_fix(
                issue_id=payload.issue_id,
                action_details=payload.action_details,
                result=payload.result,
            )
            session.commit()
        except IssueNotFoundError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return FixRead.model_validate(fix)

    def get_fix(self, fix_id: int) -> FixRead:
        session = SessionLocal()
        try:
            fix_repository = SqlAlchemyFixRepository(session)
            issue_repository = SqlAlchemyIssueRepository(session)
            service = FixService(fix_repository, issue_repository)
            fix = service.get_fix(fix_id)
        finally:
            session.close()

        if fix is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fix not found")
        return FixRead.model_validate(fix)


issue_router = IssueRoutes().router
fix_router = FixRoutes().router
