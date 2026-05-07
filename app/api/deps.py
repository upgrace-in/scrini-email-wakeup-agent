from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.agent.orchestrator import EmailAgentOrchestrator
from app.calendar.stub import StubCalendar
from app.config import Settings, get_settings
from app.storage.database import session_factory
from app.storage.repository import ConversationRepository


def db_session_dependency() -> Generator[Session, None, None]:
    SessionLocal = session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def orchestrator_factory(settings: Settings, repo: ConversationRepository) -> EmailAgentOrchestrator:
    calendar = StubCalendar(settings.stub_slot_list())
    return EmailAgentOrchestrator(settings=settings, repo=repo, calendar=calendar)
