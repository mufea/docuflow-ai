from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DOCUFLOW_ENV", "test")
os.environ.setdefault("DOCUFLOW_SECRET_KEY", "test-secret-key-please-change")
os.environ.setdefault("JOB_BROKER", "inline")
os.environ.setdefault("STORAGE_BACKEND", "filesystem")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DOCUFLOW_CORS_ORIGINS", "http://testserver")

from docuflow.config import Settings, reset_settings
from docuflow.db import Base
from docuflow.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    reset_settings()
    return Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        storage_backend="filesystem",
        storage_local_path=str(tmp_path / "storage"),
        job_broker="inline",
        ai_provider="mock",
        cookie_secure=False,
        cors_origins="http://testserver",
        stripe_webhook_secret="whsec_test",
        midtrans_server_key="midtrans-test",
        public_web_url="http://testserver",
    )


@pytest.fixture
def app(settings: Settings):
    application = create_app(settings)
    yield application
    Base.metadata.drop_all(application.state.engine)


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str = "user@example.com") -> dict:
    client.post("/v1/auth/register", json={"email": email, "password": "super-secret-1", "name": "Ada Example"})
    response = client.post("/v1/auth/login", json={"email": email, "password": "super-secret-1"})
    assert response.status_code == 200, response.text
    return {"csrf": client.cookies.get("df_csrf"), "user": response.json()}
