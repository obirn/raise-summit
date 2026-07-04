from fastapi import FastAPI

from app.api.routes import health, issues
from app.infrastructure.database import create_database


def create_app() -> FastAPI:
    app = FastAPI(title="Service Architecture Skeleton")

    @app.on_event("startup")
    def on_startup() -> None:
        create_database()

    app.include_router(health.router)
    app.include_router(issues.issue_router)
    app.include_router(issues.fix_router)
    return app


app = create_app()
