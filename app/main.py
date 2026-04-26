from fastapi import FastAPI

from app.auth import login_router
from app.config import settings
from app.db import init_db
from app.routes.attachments import router as attachments_router
from app.routes.audit import router as audit_router
from app.routes.dashboard import router as dashboard_router
from app.routes.ui import router as ui_router
from app.routes.use_cases import router as use_case_router
from app.seed import seed_if_empty


def create_app() -> FastAPI:
    app = FastAPI(title="AI Governance Workbench", version="0.1.0")

    init_db()
    seed_if_empty()
    app.include_router(login_router)
    app.include_router(attachments_router)
    app.include_router(use_case_router)
    app.include_router(audit_router)
    app.include_router(dashboard_router)
    app.include_router(ui_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment}

    return app


app = create_app()
