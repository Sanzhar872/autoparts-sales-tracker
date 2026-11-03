"""Тесты с БД работают на отдельной базе PostgreSQL (TEST_DATABASE_URL).

База создаётся, если её нет, и мигрируется через Alembic. Перед каждым тестом таблицы очищаются.
Рабочий DATABASE_URL из .env здесь намеренно перекрывается, чтобы тесты не тронули Supabase.
"""

import os
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/report_app_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_PASSWORD"] = "test-password"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import make_url, select, text  # noqa: E402

from app.constants import SEED_CARS  # noqa: E402
from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.models import Car  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _ensure_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True, connect_timeout=5) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')


@pytest.fixture(scope="session")
def migrated_db():
    try:
        _ensure_database()
    except psycopg.OperationalError as e:
        pytest.skip(f"PostgreSQL для тестов недоступен ({TEST_DATABASE_URL}): {e}")
    with get_engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS returns, sales, cars, alembic_version CASCADE"))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield


@pytest.fixture
def session(migrated_db):
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE returns, sales, cars RESTART IDENTITY CASCADE"))
        conn.execute(text("INSERT INTO cars (name) SELECT unnest(CAST(:names AS varchar[]))"), {"names": SEED_CARS})
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def client(session):
    from app.main import app

    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"password": "test-password"}).status_code == 200
        yield c


@pytest.fixture
def cars(session) -> dict[str, Car]:
    return {car.name: car for car in session.scalars(select(Car))}
