import os
import uuid

# Force stub generator for deterministic tests (before app import).
os.environ["GENERATOR_MODE"] = "stub"
os.environ["DATABASE_URL"] = "sqlite:///./test_quiz.db"
os.environ["PUBLIC_WS_BASE_URL"] = "ws://testserver"
os.environ["RANKED_DEFAULT_ROUNDS"] = "2"
os.environ["RANKED_ROUND_SECONDS"] = "20"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    get_settings.cache_clear()
    # fresh file each pytest session
    try:
        os.remove("test_quiz.db")
    except OSError:
        pass

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield
    try:
        os.remove("test_quiz.db")
    except OSError:
        pass


@pytest.fixture()
def client():
    get_settings.cache_clear()
    from app.services import auth_service, queue_service, ranked_service
    from app.db.session import SessionLocal

    auth_service._SESSIONS.clear()
    queue_service._TICKETS.clear()
    queue_service._USER_TICKET.clear()
    queue_service._WAITING.clear()
    ranked_service._TOPIC_CANDIDATES.clear()
    ranked_service._BAN_SUBMITTED.clear()
    ranked_service._LAST_ROUND_RESULT.clear()
    ranked_service._FINISH_META.clear()
    for task in list(ranked_service._ROUND_TIMERS.values()):
        task.cancel()
    ranked_service._ROUND_TIMERS.clear()

    # clean auth-related rows so emails don't collide across tests/reruns
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM round_answers"))
        db.execute(text("DELETE FROM rounds"))
        db.execute(text("DELETE FROM match_players"))
        db.execute(text("DELETE FROM matches"))
        db.execute(text("DELETE FROM answers"))
        db.execute(text("DELETE FROM questions"))
        db.execute(text("DELETE FROM quiz_sessions"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    finally:
        db.close()

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def unique_email():
    return f"user_{uuid.uuid4().hex[:10]}@test.com"
