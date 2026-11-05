from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from docuflow.db import Base
from docuflow.dsn import normalize_database_url
from docuflow.models import Plan, User
from docuflow.security.passwords import hash_password

pytestmark = pytest.mark.integration


def _test_database_url() -> str | None:
    raw = os.environ.get("TEST_DATABASE_URL", "").strip()
    return normalize_database_url(raw) if raw else None


@pytest.fixture(scope="session")
def pg_admin_url() -> str:
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    if not url.startswith("postgresql"):
        pytest.skip("TEST_DATABASE_URL must be PostgreSQL")
    return url


@pytest.fixture
def pg_engine(pg_admin_url: str) -> Generator[Engine, None, None]:
    admin = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
    db_name = f"df_it_{uuid.uuid4().hex[:12]}"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()
    driver_url = pg_admin_url.rsplit("/", 1)[0] + f"/{db_name}"
    engine = create_engine(driver_url, future=True, pool_size=8, max_overflow=4, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        cleanup = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
        with cleanup.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        cleanup.dispose()


@pytest.fixture
def pg_session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
def pg_session(pg_session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = pg_session_factory()
    session.add(
        Plan(
            slug="free",
            name="Free",
            monthly_credits=20,
            max_file_bytes=1_000_000,
            max_pages=10,
            max_ai_requests_per_day=2,
            features={},
        )
    )
    session.add(User(email="pg@example.com", password_hash=hash_password("super-secret-1"), name="Postgres"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
