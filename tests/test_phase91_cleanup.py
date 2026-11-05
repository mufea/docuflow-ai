from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from docuflow.config import Settings
from docuflow.jobs.retention import effective_stale_minutes, run_runtime_cleanup
from docuflow.jobs.scheduler import CleanupScheduler
from docuflow.models import Document, Job, StorageDeletion
from docuflow.services.documents import DocumentService, deletion_backoff_minutes
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload


class FlakyStorage:
    def __init__(self, inner, *, fail_times: int = 1, permanent: bool = False) -> None:
        self.inner = inner
        self.fail_times = fail_times
        self.permanent = permanent
        self.delete_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def delete(self, key: str) -> None:
        self.delete_calls += 1
        if self.permanent or self.delete_calls <= self.fail_times:
            raise RuntimeError("TransientStorageError")
        self.inner.delete(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


def test_effective_stale_minutes_never_below_worker_timeout() -> None:
    settings = Settings(job_stale_minutes=1, worker_timeout_seconds=300)
    assert effective_stale_minutes(settings) >= 7
    wide = Settings(job_stale_minutes=90, worker_timeout_seconds=300)
    assert effective_stale_minutes(wide) == 90


def test_cleanup_scheduler_disabled_when_interval_is_zero(settings: Settings, app) -> None:
    scheduler = CleanupScheduler(app.state.ctx.session_factory, app.state.ctx.storage, settings)
    scheduler.start()
    assert scheduler._thread is None


def test_recent_heartbeat_is_not_abandoned(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "live.pdf", ["live"]), session["csrf"])
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    db = app.state.ctx.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(UTC) - timedelta(hours=3)
        job.heartbeat_at = datetime.now(UTC)
        db.commit()
        stats = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        assert stats.abandoned_jobs == 0
        assert db.get(Job, job_id).status == "processing"
    finally:
        db.close()


def test_stale_job_cleanup_is_idempotent(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "old.pdf", ["old"]), session["csrf"])
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    db = app.state.ctx.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(UTC) - timedelta(hours=3)
        job.heartbeat_at = datetime.now(UTC) - timedelta(hours=3)
        db.commit()
        first = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        second = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        assert first.abandoned_jobs == 1
        assert first.refunded_credits >= 1
        assert second.abandoned_jobs == 0
        assert db.get(Job, job_id).status == "failed"
    finally:
        db.close()
    usage = client.get("/v1/billing/usage").json()
    assert usage["available"] == before
    assert usage["reserved"] == 0


def test_expired_document_is_removed_non_expired_remains(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    expired_id = _upload(client, write_text_pdf(tmp_path / "old.pdf", ["old"]), session["csrf"])
    keep_id = _upload(client, write_text_pdf(tmp_path / "new.pdf", ["new"]), session["csrf"])
    db = app.state.ctx.session_factory()
    try:
        expired = db.get(Document, expired_id)
        keep = db.get(Document, keep_id)
        assert expired is not None and keep is not None
        expired.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        expired_key = expired.storage_key
        keep_key = keep.storage_key
        stats = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        assert stats.expired_documents == 1
        assert db.get(Document, expired_id).deleted_at is not None
        assert db.get(Document, keep_id).deleted_at is None
        assert app.state.ctx.storage.exists(expired_key) is False
        assert app.state.ctx.storage.exists(keep_key) is True
    finally:
        db.close()
    assert client.get(f"/v1/documents/{expired_id}").status_code == 404
    assert client.get(f"/v1/documents/{keep_id}").status_code == 200


def test_storage_delete_retries_after_temporary_failure(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "tmp.pdf", ["tmp"]), session["csrf"])
    db = app.state.ctx.session_factory()
    flaky = FlakyStorage(app.state.ctx.storage, fail_times=1)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service = DocumentService(db, flaky, app.state.ctx.settings)
        owner = document.owner
        service.delete(owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        assert flaky.delete_calls == 1
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 1
        assert row.status == "completed"
        assert flaky.exists(row.storage_key) is False
    finally:
        db.close()


def test_storage_delete_permanent_failure_keeps_document_hidden(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "perm.pdf", ["perm"]), session["csrf"])
    db = app.state.ctx.session_factory()
    dead = FlakyStorage(app.state.ctx.storage, permanent=True)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        settings = app.state.ctx.settings
        settings.storage_delete_max_attempts = 2
        service = DocumentService(db, dead, settings)
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        service.retry_storage_deletions()
        db.refresh(row)
        assert row.status == "exhausted"
        assert row.attempts >= 2
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
        assert dead.exists(row.storage_key) is True
    finally:
        db.close()


def test_deletion_backoff_is_bounded() -> None:
    assert deletion_backoff_minutes(1) == 1
    assert deletion_backoff_minutes(8) == 60


def test_user_cannot_purge_another_users_document(client: TestClient, tmp_path: Path) -> None:
    first = register_and_login(client, "owner-clean@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "mine.pdf", ["mine"]), first["csrf"])
    client.post("/v1/auth/logout")
    register_and_login(client, "other-clean@example.com")
    denied = client.delete(
        f"/v1/documents/{doc_id}",
        headers={"X-CSRF-Token": client.cookies.get("df_csrf"), "Origin": "http://testserver"},
    )
    assert denied.status_code == 403
