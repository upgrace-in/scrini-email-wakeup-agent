from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.router import router as public_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.storage.database import dispose_engine, get_engine, init_db


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    relative = database_url.removeprefix("sqlite:///")
    path = Path(relative).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    _ensure_sqlite_parent_dir(settings.database_url)
    init_db()
    get_engine()
    yield
    dispose_engine()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Scrini Email Wake-Up Agent",
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "Autonomous outreach + negotiation + scheduling agent with persisted thread memory "
            "and reschedule loops."
        ),
    )
    application.include_router(public_router)
    return application


app = create_app()
