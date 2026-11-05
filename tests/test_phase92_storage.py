from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from docuflow.exceptions import NotFoundError, TransientError
from docuflow.jobs.clock import utc_now
from docuflow.models import Document, StorageDeletion
from docuflow.services.documents import DocumentService
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload
from tests.test_phase91_cleanup import FlakyStorage


class TimeoutStorage:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.delete_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def delete(self, key: str) -> None:
        self.delete_calls += 1
        raise TimeoutError("storage timeout")

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


class CountingStorage:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.delete_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def delete(self, key: str) -> None:
        self.delete_calls += 1
        self.inner.delete(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


class GoneStorage:
    """Object is already absent; delete must still succeed."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.delete_calls = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def delete(self, key: str) -> None:
        self.delete_calls += 1
        raise NotFoundError("Stored object was not found.")

    def exists(self, key: str) -> bool:
        return False


def _service(app, storage) -> tuple[DocumentService, object]:
    db = app.state.ctx.session_factory()
    return DocumentService(db, storage, app.state.ctx.settings), db


def test_successful_storage_deletion(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "ok.pdf", ["ok"]), auth["csrf"])
    db = app.state.ctx.session_factory()
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        key = document.storage_key
        service = DocumentService(db, app.state.ctx.storage, app.state.ctx.settings)
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "completed"
        assert app.state.ctx.storage.exists(key) is False
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
    finally:
        db.close()


def test_repeated_deletion_is_idempotent(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "rep.pdf", ["rep"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    service, db = _service(app, counted)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "completed"
        first_calls = counted.delete_calls
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 0
        assert result["retries"] == 0
        assert row.status == "completed"
        assert counted.delete_calls == first_calls
    finally:
        db.close()


def test_storage_provider_timeout_is_retried(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "to.pdf", ["to"]), auth["csrf"])
    timed = TimeoutStorage(app.state.ctx.storage)
    service, db = _service(app, timed)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        assert row.last_error is not None
        assert "TimeoutError" in row.last_error
        assert timed.delete_calls == 1
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
    finally:
        db.close()


def test_transient_failure_then_successful_retry(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "tmp.pdf", ["tmp"]), auth["csrf"])
    flaky = FlakyStorage(app.state.ctx.storage, fail_times=1)
    service, db = _service(app, flaky)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        row.next_attempt_at = utc_now() - timedelta(seconds=1)
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 1
        assert row.status == "completed"
        assert flaky.exists(row.storage_key) is False
    finally:
        db.close()


def test_expired_in_progress_deletion_is_reclaimed(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "stuck.pdf", ["stuck"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    service, db = _service(app, counted)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        owner = document.owner
        document.deleted_at = datetime.now(UTC)
        row = service._enqueue_deletion(document.id, document.storage_key)
        row.status = "in_progress"
        row.attempts = 1
        row.started_at = utc_now() - timedelta(minutes=30)
        row.lease_until = utc_now() - timedelta(minutes=10)
        row.owner_token = "dead-worker"
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 1
        assert row.status == "completed"
        assert row.owner_token is None
        assert counted.delete_calls == 1
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
        assert owner.id
    finally:
        db.close()


def test_process_crash_recovery_for_storage_delete(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "crash.pdf", ["crash"]), auth["csrf"])
    gone = GoneStorage(app.state.ctx.storage)
    service, db = _service(app, gone)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        document.deleted_at = datetime.now(UTC)
        row = service._enqueue_deletion(document.id, document.storage_key)
        row.status = "in_progress"
        row.attempts = 1
        row.lease_until = utc_now() - timedelta(minutes=20)
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 1
        assert row.status == "completed"
        assert gone.delete_calls == 1
    finally:
        db.close()


def test_active_lease_blocks_concurrent_deletion_claim(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "lock.pdf", ["lock"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    service, db = _service(app, counted)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        document.deleted_at = datetime.now(UTC)
        row = service._enqueue_deletion(document.id, document.storage_key)
        row.status = "in_progress"
        row.attempts = 1
        row.lease_until = utc_now() + timedelta(minutes=5)
        row.owner_token = "still-running"
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["retries"] == 0
        assert result["deleted"] == 0
        assert row.status == "in_progress"
        assert row.owner_token == "still-running"
        assert counted.delete_calls == 0
    finally:
        db.close()


def test_permanent_failure_is_exhausted_and_hides_document(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "perm.pdf", ["perm"]), auth["csrf"])
    dead = FlakyStorage(app.state.ctx.storage, permanent=True)
    service, db = _service(app, dead)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        settings = app.state.ctx.settings
        settings.storage_delete_max_attempts = 2
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        row.next_attempt_at = utc_now() - timedelta(seconds=1)
        db.commit()
        service.retry_storage_deletions()
        db.refresh(row)
        assert row.status == "exhausted"
        assert row.attempts >= 2
        assert row.last_error is not None
        assert client.get(f"/v1/documents/{doc_id}").status_code == 404
        assert dead.exists(row.storage_key) is True
    finally:
        db.close()


def test_transient_error_type_is_recorded(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "tr.pdf", ["tr"]), auth["csrf"])

    class Transient(FlakyStorage):
        def delete(self, key: str) -> None:
            self.delete_calls += 1
            raise TransientError("Object storage is unavailable.")

    flaky = Transient(app.state.ctx.storage, fail_times=1)
    service, db = _service(app, flaky)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        assert row.last_error is not None
        assert "TransientError" in row.last_error
    finally:
        db.close()


def test_current_owner_completes_and_fails_deletion(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    ok_id = _upload(client, write_text_pdf(tmp_path / "own-ok.pdf", ["ok"]), auth["csrf"])
    fail_id = _upload(client, write_text_pdf(tmp_path / "own-fail.pdf", ["fail"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    service, db = _service(app, counted)
    try:
        ok_doc = db.get(Document, ok_id)
        fail_doc = db.get(Document, fail_id)
        assert ok_doc is not None and fail_doc is not None
        service.delete(ok_doc.owner, ok_id)
        ok_row = db.query(StorageDeletion).filter_by(document_id=ok_id).one()
        assert ok_row.status == "completed"
        assert ok_row.owner_token is None
        timed = TimeoutStorage(app.state.ctx.storage)
        failing = DocumentService(db, timed, app.state.ctx.settings)
        failing.delete(fail_doc.owner, fail_id)
        fail_row = db.query(StorageDeletion).filter_by(document_id=fail_id).one()
        assert fail_row.status == "failed"
        assert fail_row.owner_token is None
        assert fail_row.last_error is not None
        assert "TimeoutError" in fail_row.last_error
    finally:
        db.close()


def test_expired_in_progress_lease_is_reclaimed_by_second_process(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "reclaim.pdf", ["reclaim"]), auth["csrf"])
    counted = CountingStorage(app.state.ctx.storage)
    first, db = _service(app, counted)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        document.deleted_at = datetime.now(UTC)
        row = first._enqueue_deletion(document.id, document.storage_key)
        row.status = "in_progress"
        row.attempts = 1
        row.owner_token = "old-owner"
        row.lease_until = utc_now() - timedelta(minutes=10)
        db.commit()
        second = DocumentService(app.state.ctx.session_factory(), counted, app.state.ctx.settings)
        try:
            result = second.retry_storage_deletions()
            stored = second.session.query(StorageDeletion).filter_by(document_id=doc_id).one()
            assert result["deleted"] == 1
            assert stored.status == "completed"
            assert stored.owner_token is None
        finally:
            second.session.close()
    finally:
        db.close()


def test_old_deletion_worker_cannot_overwrite_or_clear_new_owner(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "race.pdf", ["race"]), auth["csrf"])
    stolen = {"token": "new-owner"}

    class StealOnDelete:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.delete_calls = 0

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        def delete(self, key: str) -> None:
            self.delete_calls += 1
            other = app.state.ctx.session_factory()
            try:
                row = other.query(StorageDeletion).filter_by(storage_key=key).one()
                row.status = "in_progress"
                row.owner_token = stolen["token"]
                row.lease_until = utc_now() + timedelta(minutes=5)
                other.commit()
            finally:
                other.close()

        def exists(self, key: str) -> bool:
            return self.inner.exists(key)

    steal = StealOnDelete(app.state.ctx.storage)
    service, db = _service(app, steal)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        check = app.state.ctx.session_factory()
        try:
            stored = check.query(StorageDeletion).filter_by(document_id=doc_id).one()
            assert stored.status == "in_progress"
            assert stored.owner_token == "new-owner"
            assert stored.lease_until is not None
            assert steal.delete_calls == 1
            finished = DocumentService(check, app.state.ctx.storage, app.state.ctx.settings)
            assert (
                finished._finish_owned_deletion(
                    stored.id,
                    "old-token-that-is-not-new-owner",
                    success=True,
                )
                is False
            )
            check.refresh(stored)
            assert stored.status == "in_progress"
            assert stored.owner_token == "new-owner"
            assert finished._renew_deletion_lease(stored.id, "old-token-that-is-not-new-owner", 5) is False
            check.refresh(stored)
            assert stored.owner_token == "new-owner"
            assert finished._finish_owned_deletion(stored.id, "new-owner", success=True) is True
            check.refresh(stored)
            assert stored.status == "completed"
            assert stored.owner_token is None
        finally:
            check.close()
    finally:
        db.close()
