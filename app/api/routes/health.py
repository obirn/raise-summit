from fastapi import APIRouter


class HealthRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(tags=["health"])
        self.router.add_api_route("/health", self.health_check, methods=["GET"])

    def health_check(self) -> dict[str, str]:
        return {"status": "ok"}


router = HealthRoutes().router
