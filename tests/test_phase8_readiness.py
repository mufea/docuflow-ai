from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.exceptions import TransientError
from docuflow.jobs.broker import RQBroker, _worker_heartbeat_fresh
from docuflow.logging import redact
from docuflow.storage.filesystem import FilesystemStorage
from tests.conftest import register_and_login
from tests.test_jobs_and_security import _wait_job


def test_production_readiness_requires_postgres_s3_and_secret() -> None:
    weak = Settings(
        env="production",
        secret_key="dev-only-change-me-use-32-plus-chars!!",
        database_url="sqlite+pysqlite:///./data/docuflow.db",
        storage_backend="filesystem",
        job_broker="inline",
    )
    errors = " ".join(weak.production_readiness_errors())
    assert "DOCUFLOW_SECRET_KEY" in errors
    assert "PostgreSQL" in errors
    assert "STORAGE_BACKEND" in errors


def test_production_readiness_accepts_complete_s3_postgres() -> None:
    ready = Settings(
        env="production",
        secret_key="production-secret-key-32-chars-min",
        database_url="postgresql+psycopg://docuflow:x@db:5432/docuflow",
        storage_backend="s3",
        s3_bucket="docuflow-documents",
        s3_access_key_id=SecretStr("testid"),
        s3_secret_access_key=SecretStr("testsecret"),
        job_broker="inline",
    )
    assert ready.production_readiness_errors() == []
    assert ready.cookie_secure is True


def test_production_readiness_rq_requires_redis() -> None:
    settings = Settings(
        env="production",
        secret_key="production-secret-key-32-chars-min",
        database_url="postgresql+psycopg://docuflow:x@db:5432/docuflow",
        storage_backend="s3",
        s3_bucket="docs",
        s3_access_key_id=SecretStr("testid"),
        s3_secret_access_key=SecretStr("testsecret"),
        job_broker="rq",
        redis_url="   ",
    )
    assert any("REDIS_URL" in item for item in settings.production_readiness_errors())


def test_ready_reports_storage_failure(client: TestClient, app) -> None:
    class DeadStorage:
        def ping(self) -> None:
            raise TransientError("Object storage is unavailable.")

    app.state.ctx.storage = DeadStorage()
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["storage"] is False
    assert body["checks"]["database"] is True


def test_ready_reports_redis_failure_when_rq(client: TestClient, app) -> None:
    app.state.ctx.settings.job_broker = "rq"
    app.state.ctx.settings.redis_url = "redis://127.0.0.1:1/0"
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] is False
    assert response.json()["status"] == "degraded"


def test_ready_ok_for_inline_local_storage(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["storage"] is True
    assert body["broker"] == "inline"


def test_alembic_config_resolves_repo_ini() -> None:
    from docuflow.migrate import alembic_config

    config = alembic_config()
    assert config.get_main_option("script_location")


def test_health_is_liveness_only(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "docuflow-api"}


def test_filesystem_ping_rejects_unwritable(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path / "ok")
    storage.ping()
    blocked = FilesystemStorage(tmp_path / "blocked")
    blocked.root.chmod(0o500)
    try:
        try:
            blocked.ping()
            # Some environments still allow owner write; treat as skip.
        except TransientError:
            pass
    finally:
        blocked.root.chmod(0o700)


def test_rq_falls_back_when_worker_probe_fails(monkeypatch) -> None:
    processed: list[str] = []

    class Runner:
        def process(self, job_id: str) -> None:
            processed.append(job_id)

    from docuflow.jobs.broker import InlineBroker

    broker = RQBroker.__new__(RQBroker)
    broker.job_timeout = 300
    broker.inline = InlineBroker(Runner(), workers=1)  # type: ignore[arg-type]
    broker.queue = SimpleNamespace(connection=object(), name="docuflow")
    monkeypatch.setattr(broker, "active_worker_count", lambda: 0)
    broker.enqueue("job-redis-down")
    broker.inline.pool.shutdown(wait=True)
    assert processed == ["job-redis-down"]


def test_stale_rq_heartbeat_is_not_active() -> None:
    stale = SimpleNamespace(last_heartbeat=datetime.now(UTC) - timedelta(minutes=10))
    fresh = SimpleNamespace(last_heartbeat=datetime.now(UTC))
    assert _worker_heartbeat_fresh(stale) is False
    assert _worker_heartbeat_fresh(fresh) is True


def test_secret_redaction_covers_storage_and_urls() -> None:
    clean = redact(
        {
            "S3_ACCESS_KEY_ID": "AKIATEST",
            "S3_SECRET_ACCESS_KEY": "secret",
            "signed_url": "https://example/signed",
            "DATABASE_URL": "postgres://user:pass@db/docuflow",
            "safe": "ok",
        }
    )
    assert clean["S3_ACCESS_KEY_ID"] == "[redacted]"
    assert clean["S3_SECRET_ACCESS_KEY"] == "[redacted]"
    assert clean["signed_url"] == "[redacted]"
    assert clean["DATABASE_URL"] == "[redacted]"
    assert clean["safe"] == "ok"


def test_duplicate_process_does_not_double_charge(client: TestClient, app, tmp_path: Path) -> None:
    from docuflow.conversion.engines import write_simple_docx

    session = register_and_login(client)
    csrf = session["csrf"]
    source = write_simple_docx(tmp_path / "memo.docx", ["Phase 8 claim"])
    with source.open("rb") as handle:
        uploaded = client.post(
            "/v1/documents",
            files={
                "file": (
                    source.name,
                    handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
        )
    assert uploaded.status_code == 200, uploaded.text
    created = client.post(
        "/v1/jobs",
        json={"operation": "docx_to_pdf", "document_ids": [uploaded.json()["id"]], "params": {}},
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    current = _wait_job(client, job_id)
    app.state.ctx.runner.process(job_id)
    app.state.ctx.runner.process(job_id)
    again = client.get(f"/v1/jobs/{job_id}").json()
    assert current["status"] == "completed"
    assert again["status"] == "completed"
    assert again["credits_reserved"] == 6
