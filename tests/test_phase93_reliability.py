from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ReadTimeoutError
from fastapi.testclient import TestClient
from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.exceptions import TransientError
from docuflow.jobs.clock import utc_now
from docuflow.jobs.leases import LEASE_NAME, acquire_lease, lease_owner
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.models import CleanupLease, Document, StorageDeletion
from docuflow.services.documents import DocumentService
from docuflow.storage.s3 import S3Storage
from docuflow.storage.timeouts import S3_RETRY_ATTEMPTS, storage_call_timeout_seconds
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload
from tests.test_phase92_storage import CountingStorage, _service


def test_storage_http_timeout_stays_under_half_the_lease() -> None:
    for lease_minutes in (1, 5, 15):
        timeout = storage_call_timeout_seconds(lease_minutes)
        lease_seconds = lease_minutes * 60
        assert 5 <= timeout <= 60
        assert timeout * S3_RETRY_ATTEMPTS <= lease_seconds // 2


def test_s3_client_uses_bounded_timeouts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_client(service: str, **kwargs):
        assert service == "s3"
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("docuflow.storage.s3.boto3.client", fake_client)
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        storage_backend="s3",
        s3_access_key_id=SecretStr("test-key"),
        s3_secret_access_key=SecretStr("test-secret"),
        s3_bucket="docuflow-test",
        storage_delete_lease_minutes=5,
    )
    S3Storage(settings)
    config = captured["config"]
    expected = storage_call_timeout_seconds(5)
    assert config.connect_timeout <= expected
    assert config.read_timeout == expected
    assert config.retries["max_attempts"] == S3_RETRY_ATTEMPTS
    assert expected * S3_RETRY_ATTEMPTS < 5 * 60


def test_s3_timeout_on_delete_and_exists_is_transient(monkeypatch) -> None:
    client = MagicMock()
    client.delete_object.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid", error="timed out")
    client.head_object.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid", error="timed out")
    monkeypatch.setattr("docuflow.storage.s3.boto3.client", lambda *args, **kwargs: client)
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        storage_backend="s3",
        s3_access_key_id=SecretStr("test-key"),
        s3_secret_access_key=SecretStr("test-secret"),
        s3_bucket="docuflow-test",
    )
    storage = S3Storage(settings)
    try:
        storage.delete("user/object.bin")
        raise AssertionError("delete should time out")
    except TransientError as exc:
        assert "timed out" in str(exc).lower() or "timeout" in type(exc).__name__.lower()
    try:
        storage.exists("user/object.bin")
        raise AssertionError("exists should not treat a timeout as missing")
    except TransientError:
        pass


def test_heartbeat_false_stops_remaining_storage_deletes(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    first_id = _upload(client, write_text_pdf(tmp_path / "a.pdf", ["a"]), auth["csrf"])
    second_id = _upload(client, write_text_pdf(tmp_path / "b.pdf", ["b"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    service, db = _service(app, counted)
    try:
        for doc_id in (first_id, second_id):
            document = db.get(Document, doc_id)
            assert document is not None
            document.deleted_at = datetime.now(UTC)
            service._enqueue_deletion(document.id, document.storage_key)
        db.commit()
        beats = {"n": 0}

        def heartbeat() -> bool:
            beats["n"] += 1
            return beats["n"] == 1

        result = service.retry_storage_deletions(heartbeat=heartbeat)
        assert result["deleted"] == 1
        assert result["retries"] == 1
        assert counted.delete_calls == 1
        pending = [
            row.status
            for row in db.query(StorageDeletion).filter(StorageDeletion.document_id.in_((first_id, second_id)))
        ]
        assert pending.count("completed") == 1
        assert pending.count("pending") == 1
    finally:
        db.close()


def test_lost_cleanup_lease_stops_remaining_storage_deletes(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    first_id = _upload(client, write_text_pdf(tmp_path / "c.pdf", ["c"]), auth["csrf"])
    second_id = _upload(client, write_text_pdf(tmp_path / "d.pdf", ["d"]), auth["csrf"])
    inner = app.state.ctx.storage

    class StealCleanupOnDelete:
        def __init__(self) -> None:
            self.delete_calls = 0

        def __getattr__(self, name: str):
            return getattr(inner, name)

        def delete(self, key: str) -> None:
            self.delete_calls += 1
            if self.delete_calls == 1:
                other = app.state.ctx.session_factory()
                try:
                    row = other.get(CleanupLease, LEASE_NAME)
                    assert row is not None
                    row.lease_until = utc_now() - timedelta(seconds=5)
                    other.commit()
                    assert acquire_lease(other, "replacement-owner", ttl=timedelta(minutes=5)) is True
                finally:
                    other.close()
            inner.delete(key)

        def exists(self, key: str) -> bool:
            return inner.exists(key)

    steal = StealCleanupOnDelete()
    service, db = _service(app, steal)
    try:
        for doc_id in (first_id, second_id):
            document = db.get(Document, doc_id)
            assert document is not None
            document.deleted_at = datetime.now(UTC)
            service._enqueue_deletion(document.id, document.storage_key)
        db.commit()
    finally:
        db.close()
    cleanup_session = app.state.ctx.session_factory()
    holder = app.state.ctx.session_factory()
    try:
        stats = run_runtime_cleanup(cleanup_session, steal, app.state.ctx.settings)
        assert stats.aborted is True
        assert steal.delete_calls == 1
        assert stats.storage_deleted == 1
        assert lease_owner(holder) == "replacement-owner"
    finally:
        cleanup_session.close()
        holder.close()
    check = app.state.ctx.session_factory()
    try:
        statuses = [
            row.status
            for row in check.query(StorageDeletion).filter(StorageDeletion.document_id.in_((first_id, second_id)))
        ]
        assert statuses.count("completed") == 1
        assert statuses.count("pending") == 1
    finally:
        check.close()


def test_stale_owner_cannot_finish_after_lease_expires_during_delete(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "slow.pdf", ["slow"]), auth["csrf"])

    class ExpireThenReclaim:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.delete_calls = 0

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        def delete(self, key: str) -> None:
            self.delete_calls += 1
            if self.delete_calls > 1:
                self.inner.delete(key)
                return
            other = app.state.ctx.session_factory()
            try:
                row = other.query(StorageDeletion).filter_by(storage_key=key).one()
                row.lease_until = utc_now() - timedelta(minutes=10)
                other.commit()
            finally:
                other.close()
            reclaimer = DocumentService(app.state.ctx.session_factory(), self.inner, app.state.ctx.settings)
            try:
                result = reclaimer.retry_storage_deletions()
                assert result["deleted"] == 1
            finally:
                reclaimer.session.close()

        def exists(self, key: str) -> bool:
            return False

    steal = ExpireThenReclaim(app.state.ctx.storage)
    service, db = _service(app, steal)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        stored = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        db.refresh(stored)
        assert stored.status == "completed"
        assert stored.owner_token is None
        assert steal.delete_calls >= 1
        assert service._finish_owned_deletion(stored.id, "old-owner-that-lost-the-lease", success=True) is False
        db.refresh(stored)
        assert stored.status == "completed"
    finally:
        db.close()
