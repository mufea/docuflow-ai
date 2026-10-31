from __future__ import annotations

from fastapi.testclient import TestClient

from docuflow.config import Settings, reset_settings
from docuflow.db import Base
from docuflow.email.backend import EmailBackend
from docuflow.main import create_app
from tests.conftest import register_and_login


def test_register_login_me_logout(client: TestClient) -> None:
    created = client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "super-secret-1", "name": "Ada"},
    )
    assert created.status_code == 200
    assert created.json()["credits_available"] == 50
    login = client.post("/v1/auth/login", json={"email": "ada@example.com", "password": "super-secret-1"})
    assert login.status_code == 200
    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 200
    denied = client.get("/v1/auth/me")
    assert denied.status_code == 401


def test_invalid_login_is_generic(client: TestClient) -> None:
    client.post("/v1/auth/register", json={"email": "ada@example.com", "password": "super-secret-1", "name": "Ada"})
    response = client.post("/v1/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert "password" not in response.json()["message"].lower() or "invalid" in response.json()["message"].lower()


def test_csrf_required_for_profile_update(client: TestClient) -> None:
    register_and_login(client)
    missing = client.patch("/v1/auth/me", json={"name": "Hacker"})
    assert missing.status_code == 403
    csrf = client.cookies.get("df_csrf")
    ok = client.patch(
        "/v1/auth/me", json={"name": "Grace"}, headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"}
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "Grace"


def test_register_succeeds_when_verify_email_fails(client: TestClient, app) -> None:
    class BoomEmail(EmailBackend):
        def send(self, *, to: str, subject: str, body: str) -> None:
            raise RuntimeError("smtp down")

    app.state.ctx.email = BoomEmail()
    created = client.post(
        "/v1/auth/register",
        json={"email": "mailfail@example.com", "password": "super-secret-1", "name": "Mail Fail"},
    )
    assert created.status_code == 200
    assert created.json()["email"] == "mailfail@example.com"


def test_production_unknown_host_returns_json(tmp_path) -> None:
    reset_settings()
    settings = Settings(
        env="production",
        secret_key="test-secret-key-please-change",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'prod-host.db'}",
        storage_backend="filesystem",
        storage_local_path=str(tmp_path / "storage"),
        job_broker="inline",
        ai_provider="mock",
        cookie_secure=False,
        trusted_hosts=".onrender.com",
        public_api_url="https://docuflow-api.onrender.com",
        public_web_url="https://pdf.example.com",
        cors_origins="https://pdf.example.com",
    )
    application = create_app(settings)
    try:
        with TestClient(application, base_url="https://evil.example") as client:
            rejected = client.get("/health")
        assert rejected.status_code == 400
        assert rejected.headers["content-type"].startswith("application/json")
        assert "Host header" in rejected.json()["message"]
        with TestClient(application, base_url="https://docuflow-api.onrender.com") as allowed:
            ok = allowed.get("/health")
        assert ok.status_code == 200
        with TestClient(application, base_url="https://pdf.example.com") as custom:
            custom_ok = custom.get("/health")
        assert custom_ok.status_code == 200
    finally:
        Base.metadata.drop_all(application.state.engine)
