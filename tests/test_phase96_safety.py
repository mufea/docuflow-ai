from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from docuflow.config import ProductionConfigError, Settings, reset_settings
from docuflow.exceptions import TransientError
from docuflow.jobs.recovery import recover_queued_jobs
from docuflow.jobs.retention import cleanup_abandoned_jobs
from docuflow.main import create_app
from docuflow.models import Job
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload, _wait_job
from tests.test_phase9_integrity import _persistent_settings


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "production",
        "secret_key": "production-secret-key-32-chars-min",
        "database_url": "postgresql+psycopg://docuflow:x@db:5432/docuflow",
        "storage_backend": "s3",
        "s3_bucket": "docuflow-documents",
        "s3_access_key_id": SecretStr("testid"),
        "s3_secret_access_key": SecretStr("testsecret"),
        "job_broker": "inline",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_valid_production_configuration_has_no_critical_errors() -> None:
    ready = _production()
    assert ready.production_readiness_errors() == []
    warnings = ready.production_readiness_warnings()
    assert any("AI_PROVIDER" in item for item in warnings)
    assert any("EMAIL_BACKEND" in item for item in warnings)


def test_production_fail_fast_on_default_secret(caplog) -> None:
    weak = _production(
        secret_key="dev-only-change-me-use-32-plus-chars!!",
        database_url="sqlite+pysqlite:///./data/docuflow.db",
        storage_backend="filesystem",
        s3_access_key_id=None,
        s3_secret_access_key=None,
    )
    caplog.set_level(logging.ERROR)
    with pytest.raises(ProductionConfigError) as caught:
        create_app(weak)
    assert caught.value.errors
    assert "DOCUFLOW_SECRET_KEY" in " ".join(caught.value.errors)
    assert "dev-only-change-me-use-32-plus-chars!!" not in caplog.text
    assert "sqlite+pysqlite" not in caplog.text


def test_production_rejects_short_or_repeated_secret() -> None:
    short = _production(secret_key="short-but-sixteen!!")
    assert any("DOCUFLOW_SECRET_KEY" in item for item in short.production_readiness_errors())
    repeated = _production(secret_key="a" * 32)
    assert any("DOCUFLOW_SECRET_KEY" in item for item in repeated.production_readiness_errors())
    with pytest.raises(ValidationError):
        Settings(env="production", secret_key="too-short")


def test_production_rejects_sqlite_and_missing_s3() -> None:
    sqlite = _production(database_url="sqlite+pysqlite:///./data/docuflow.db")
    assert any("PostgreSQL" in item for item in sqlite.production_readiness_errors())
    missing = _production(s3_access_key_id=None, s3_secret_access_key=None)
    assert any("S3_ACCESS_KEY_ID" in item for item in missing.production_readiness_errors())
    with pytest.raises(ProductionConfigError):
        create_app(_production(database_url="sqlite+pysqlite:///./data/docuflow.db", storage_backend="filesystem"))


def test_redis_required_only_for_rq() -> None:
    inline = _production(job_broker="inline", redis_url="")
    assert inline.production_readiness_errors() == []
    rq_missing = _production(job_broker="rq", redis_url="   ")
    assert any("REDIS_URL" in item for item in rq_missing.production_readiness_errors())
    rq_invalid = _production(job_broker="rq", redis_url="https://example.invalid/not-redis")
    assert any("REDIS_URL" in item for item in rq_invalid.production_readiness_errors())
    rq_ok = _production(job_broker="rq", redis_url="rediss://cache.internal:6379/0")
    assert rq_ok.production_readiness_errors() == []


def test_development_startup_allows_sqlite(settings: Settings) -> None:
    app = create_app(settings)
    assert app.state.ctx.settings.env == "test"
    assert app.state.ctx.settings.job_broker == "inline"


def test_ready_healthy_is_http_200(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_database_failure_is_http_503(client: TestClient, app) -> None:
    class DeadSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("postgres://user:supersecret@db/docuflow")

        def close(self) -> None:
            return None

    app.state.ctx.session_factory = lambda: DeadSession()
    response = client.get("/ready")
    assert response.status_code == 503
    assert "supersecret" not in response.text
    assert "postgres://" not in response.text
    assert response.json()["checks"]["database"] is False


def test_health_stays_200_when_storage_is_down(client: TestClient, app) -> None:
    class DeadStorage:
        def ping(self) -> None:
            raise TransientError("Object storage is unavailable.")

    app.state.ctx.storage = DeadStorage()
    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "docuflow-api"}
    assert ready.status_code == 503
    assert ready.json()["status"] == "degraded"


def test_optional_redis_does_not_fail_inline_readiness(client: TestClient, app) -> None:
    app.state.ctx.settings.job_broker = "inline"
    app.state.ctx.settings.redis_url = "redis://127.0.0.1:1/0"
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["redis"] is True
    assert response.json()["broker"] == "inline"


def test_restart_recovers_queued_job_once(tmp_path: Path) -> None:
    settings = _persistent_settings(tmp_path)
    first = create_app(settings)
    with TestClient(first) as client:
        auth = register_and_login(client, "recover@example.com")
        before = client.get("/v1/billing/usage").json()["available"]
        doc_id = _upload(client, write_text_pdf(tmp_path / "queued.pdf", ["queued"]), auth["csrf"])
        first.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
        created = client.post(
            "/v1/jobs",
            json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
            headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
        )
        assert created.status_code == 200, created.text
        job_id = created.json()["id"]
        assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "queued"
        reserved = client.get("/v1/billing/usage").json()
        assert reserved["reserved"] >= 1

    first.state.engine.dispose()
    reset_settings()
    restarted = create_app(settings)
    with TestClient(restarted) as client:
        login = client.post("/v1/auth/login", json={"email": "recover@example.com", "password": "super-secret-1"})
        assert login.status_code == 200, login.text
        job = _wait_job(client, job_id)
        assert job["status"] == "completed"
        restarted.state.ctx.runner.process(job_id)
        restarted.state.ctx.runner.process(job_id)
        again = client.get(f"/v1/jobs/{job_id}").json()
        assert again["status"] == "completed"
        after = client.get("/v1/billing/usage").json()
        assert after["reserved"] == 0
        assert after["available"] == before - again["credits_reserved"]


def test_recovery_skips_processing_jobs_and_cleanup_fails_stale(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client, "stale-recover@example.com")
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "stuck.pdf", ["stuck"]), auth["csrf"])
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    db = app.state.ctx.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(UTC) - timedelta(hours=2)
        job.heartbeat_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    finally:
        db.close()
    assert recover_queued_jobs(app.state.ctx.session_factory, app.state.ctx.broker) == 0
    db = app.state.ctx.session_factory()
    try:
        cleanup_abandoned_jobs(db, stale_minutes=45)
        stuck = db.get(Job, job_id)
        assert stuck is not None
        assert stuck.status == "failed"
        assert stuck.error_code == "timeout"
    finally:
        db.close()
    after = client.get("/v1/billing/usage").json()
    assert after["available"] == before
    assert after["reserved"] == 0


def test_duplicate_recovery_does_not_double_charge(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client, "dup-recover@example.com")
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "dup.pdf", ["dup"]), auth["csrf"])
    original = app.state.ctx.broker.enqueue
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    app.state.ctx.broker.enqueue = original
    assert recover_queued_jobs(app.state.ctx.session_factory, app.state.ctx.broker) == 1
    assert recover_queued_jobs(app.state.ctx.session_factory, app.state.ctx.broker) >= 0
    job = _wait_job(client, job_id)
    assert job["status"] == "completed"
    app.state.ctx.runner.process(job_id)
    after = client.get("/v1/billing/usage").json()
    assert after["reserved"] == 0
    assert after["available"] == before - job["credits_reserved"]
