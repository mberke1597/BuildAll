from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db, engine
from app.db.base import Base
from app.routes import (
    auth, projects, chat, media, documents, ask, parcel, cost,
    health, users, analytics, assistant, dashboard, copilot_tools, agents,
)
from app.core.deps import get_current_user
from app.services.storage import ensure_bucket
from app.seed import seed_data


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Existing routers
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(chat.router)
    app.include_router(media.router)
    app.include_router(documents.router)
    app.include_router(ask.router)
    app.include_router(parcel.router)
    app.include_router(cost.router)
    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(analytics.router)
    app.include_router(assistant.router)
    app.include_router(dashboard.router)
    app.include_router(copilot_tools.router)

    # NEW: Agent framework endpoints
    app.include_router(agents.router)

    @app.get("/me")
    def me_alias(user=Depends(get_current_user)):
        return user

    @app.on_event("startup")
    def _startup():
        import os

        # Hard kill-switch for PaaS (Railway/Render) deploys
        if os.getenv("SKIP_STARTUP", "false").lower() == "true":
            return

        # In production: NEVER auto-create schema. Use Alembic migrations.
        auto_create = os.getenv("DB_AUTO_CREATE", "false").lower() == "true"
        if auto_create:
            Base.metadata.create_all(bind=engine)

        # Storage bucket setup can fail if MinIO isn't configured; make it optional
        if os.getenv("ENABLE_STORAGE", "false").lower() == "true":
            ensure_bucket()

        # Seeding should be optional; only run when explicitly enabled
        if os.getenv("SEED_DATA", "false").lower() == "true":
            db: Session = next(get_db())
            seed_data(db)

    @app.websocket("/ws/projects/{project_id}")
    async def ws_project(websocket, project_id: int, token: str):
        db: Session = next(get_db())
        await chat.websocket_endpoint(websocket, project_id=project_id, token=token, db=db)

    return app


app = create_app()
