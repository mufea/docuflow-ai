from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError, ReadTimeoutError
from fastapi.testclient import TestClient
from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, DocuflowError, NotFoundError, TransientError
from docuflow.jobs.clock import utc_now
from docuflow.models import Document, StorageDeletion
from docuflow.storage.s3 import S3Storage, classify_s3_client_error
from docuflow.storage.timeouts import (
    S3_STANDARD_MAX_BACKOFF_SECONDS,
    S3_TOTAL_MAX_ATTEMPTS,
    storage_call_budget,
    storage_call_timeout_seconds,
)
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload
from tests.test_phase92_storage import _service


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "secret_key": "test-secret-key-please-change",
        "storage_backend": "s3",
        "s3_access_key_id": SecretStr("test-key"),
        "s3_secret_access_key": SecretStr("test-secret"),
        "s3_bucket": "docuflow-test",
        "storage_delete_lease_minutes": 5,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _s3(monkeypatch, client: MagicMock, **overrides: object) -> S3Storage:
    monkeypatch.setattr("docuflow.storage.s3.boto3.client", lambda *args, **kwargs: client)
    return S3Storage(_settings(**overrides))


def _client_error(code: str, status: int, *, message: str = "denied") -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "DeleteObject",
    )


def test_total_attempts_are_not_retries() -> None:
    budget = storage_call_budget(5)
    assert budget.total_max_attempts == S3_TOTAL_MAX_ATTEMPTS
    assert budget.retry_attempts == S3_TOTAL_MAX_ATTEMPTS - 1
    assert budget.botocore_retries["total_max_attempts"] == S3_TOTAL_MAX_ATTEMPTS
    assert "max_attempts" not in budget.botocore_retries
    assert budget.botocore_retries["mode"] == "standard"


def test_botocore_config_uses_total_max_attempts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_client(service: str, **kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("docuflow.storage.s3.boto3.client", fake_client)
    S3Storage(_settings())
    retries = captured["config"].retries
    assert retries["total_max_attempts"] == S3_TOTAL_MAX_ATTEMPTS
    assert retries.get("max_attempts") is None
    assert retries["mode"] == "standard"


def test_five_minute_lease_http_budget_stays_under_half() -> None:
    budget = storage_call_budget(5)
    assert budget.lease_seconds == 300
    assert budget.http_budget_seconds <= budget.lease_seconds // 2
    assert budget.designed_ceiling_seconds < budget.lease_seconds
    assert budget.read_timeout_seconds == storage_call_timeout_seconds(5)
    assert budget.connect_timeout_seconds <= budget.read_timeout_seconds
    assert budget.standard_max_backoff_seconds == S3_STANDARD_MAX_BACKOFF_SECONDS


def test_minimum_lease_budget_stays_under_full_lease() -> None:
    budget = storage_call_budget(1)
    assert budget.lease_seconds == 60
    assert budget.http_budget_seconds <= budget.lease_seconds // 2
    assert budget.designed_ceiling_seconds < budget.lease_seconds
    assert budget.read_timeout_seconds >= 5


def test_invalid_and_extreme_lease_values_are_clamped() -> None:
    invalid = storage_call_budget("not-a-number")
    negative = storage_call_budget(-12)
    huge = storage_call_budget(10_000)
    extra_attempts = storage_call_budget(5, attempts=99)
    assert invalid.lease_seconds == 60
    assert negative.lease_seconds == 60
    assert huge.read_timeout_seconds <= 60
    assert huge.http_budget_seconds <= huge.lease_seconds // 2
    assert extra_attempts.total_max_attempts == S3_TOTAL_MAX_ATTEMPTS
    zero_attempts = storage_call_budget(5, attempts=0)
    assert zero_attempts.total_max_attempts == 1


def test_retry_budget_uses_documented_backoff_margin() -> None:
    budget = storage_call_budget(5)
    expected_backoff = budget.retry_attempts * S3_STANDARD_MAX_BACKOFF_SECONDS
    assert budget.designed_ceiling_seconds == budget.http_budget_seconds + expected_backoff
    assert budget.designed_ceiling_seconds <= budget.lease_seconds * 2 // 3


def test_classify_missing_auth_transient_permanent() -> None:
    kind, code, status = classify_s3_client_error(_client_error("NoSuchKey", 404))
    assert (kind, code, status) == ("missing", "NoSuchKey", 404)
    kind, code, status = classify_s3_client_error(_client_error("AccessDenied", 403))
    assert kind == "authorization" and code == "AccessDenied"
    kind, _, status = classify_s3_client_error(_client_error("SlowDown", 503))
    assert kind == "transient" and status == 503
    kind, _, status = classify_s3_client_error(_client_error("InternalError", 500))
    assert kind == "transient"
    kind, code, _ = classify_s3_client_error(_client_error("NoSuchBucket", 404))
    assert kind == "permanent" and code == "NoSuchBucket"
    kind, _, _ = classify_s3_client_error(_client_error("404", 404))
    assert kind == "missing"


def test_delete_existing_object_succeeds(monkeypatch) -> None:
    client = MagicMock()
    storage = _s3(monkeypatch, client)
    storage.delete("user/object.bin")
    client.delete_object.assert_called_once_with(Bucket="docuflow-test", Key="user/object.bin")


def test_delete_already_missing_object_is_success(monkeypatch) -> None:
    client = MagicMock()
    client.delete_object.side_effect = _client_error("NoSuchKey", 404)
    storage = _s3(monkeypatch, client)
    storage.delete("user/gone.bin")


def test_access_denied_logs_classification_without_secrets(monkeypatch, caplog) -> None:
    client = MagicMock()
    client.delete_object.side_effect = _client_error(
        "AccessDenied", 403, message="https://example.invalid/signed?X-Amz-Signature=abc"
    )
    storage = _s3(monkeypatch, client)
    caplog.set_level(logging.WARNING, logger="docuflow.storage")
    try:
        storage.delete("user/secret.bin")
    except AuthorizationError:
        pass
    else:
        raise AssertionError("AccessDenied must raise")
    text = caplog.text
    assert "classification=authorization" in text
    assert "operation=delete" in text
    assert "X-Amz-Signature" not in text
    assert "signed?" not in text


def test_delete_access_denied_is_not_success(monkeypatch) -> None:
    client = MagicMock()
    client.delete_object.side_effect = _client_error("AccessDenied", 403, message="AKIAEXAMPLE")
    storage = _s3(monkeypatch, client)
    try:
        storage.delete("user/secret.bin")
        raise AssertionError("AccessDenied must not succeed")
    except AuthorizationError as exc:
        assert "AKIA" not in str(exc)
        assert "denied" in str(exc).lower() or "access" in str(exc).lower()


def test_delete_http_500_and_slowdown_are_transient(monkeypatch) -> None:
    client = MagicMock()
    storage = _s3(monkeypatch, client)
    client.delete_object.side_effect = _client_error("InternalError", 500)
    try:
        storage.delete("user/a.bin")
        raise AssertionError("500 must be transient")
    except TransientError:
        pass
    client.delete_object.side_effect = _client_error("SlowDown", 503)
    try:
        storage.delete("user/b.bin")
        raise AssertionError("SlowDown must be transient")
    except TransientError:
        pass


def test_exists_false_for_confirmed_missing(monkeypatch) -> None:
    client = MagicMock()
    client.head_object.side_effect = _client_error("NotFound", 404)
    storage = _s3(monkeypatch, client)
    assert storage.exists("user/missing.bin") is False


def test_exists_access_denied_raises(monkeypatch) -> None:
    client = MagicMock()
    client.head_object.side_effect = _client_error("AccessDenied", 403)
    storage = _s3(monkeypatch, client)
    try:
        storage.exists("user/denied.bin")
        raise AssertionError("exists must not treat AccessDenied as missing")
    except AuthorizationError:
        pass


def test_exists_temporary_failure_is_transient(monkeypatch) -> None:
    client = MagicMock()
    client.head_object.side_effect = _client_error("ServiceUnavailable", 503)
    storage = _s3(monkeypatch, client)
    try:
        storage.exists("user/flaky.bin")
        raise AssertionError("503 must not look like a missing object")
    except TransientError:
        pass


def test_download_missing_object(monkeypatch, tmp_path: Path) -> None:
    client = MagicMock()
    client.download_file.side_effect = _client_error("NoSuchKey", 404)
    storage = _s3(monkeypatch, client)
    try:
        storage.download("user/missing.bin", tmp_path / "out.bin")
        raise AssertionError("missing download must raise NotFoundError")
    except NotFoundError:
        pass


def test_upload_timeout_is_transient(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.bin"
    source.write_bytes(b"pdf")
    client = MagicMock()
    client.upload_file.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid", error="timed out")
    storage = _s3(monkeypatch, client)
    try:
        storage.put("user/in.bin", source, "application/pdf")
        raise AssertionError("upload timeout must be transient")
    except TransientError as exc:
        assert "timed out" in str(exc).lower()


def test_ping_failure_classifies_auth_and_transient(monkeypatch) -> None:
    client = MagicMock()
    storage = _s3(monkeypatch, client)
    client.head_bucket.side_effect = _client_error("AccessDenied", 403)
    try:
        storage.ping()
        raise AssertionError("denied ping must not look healthy")
    except AuthorizationError:
        pass
    client.head_bucket.side_effect = _client_error("ServiceUnavailable", 503)
    try:
        storage.ping()
        raise AssertionError("503 ping must be transient")
    except TransientError:
        pass
    client.head_bucket.side_effect = _client_error("NoSuchBucket", 400)
    try:
        storage.ping()
        raise AssertionError("missing bucket must not be ignored")
    except DocuflowError:
        pass


def test_authorization_failure_is_not_marked_deleted(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client, email="denied@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "deny.pdf", ["deny"]), auth["csrf"])

    class DeniedStorage:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.delete_calls = 0

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        def delete(self, key: str) -> None:
            self.delete_calls += 1
            raise AuthorizationError("Object storage access was denied.")

        def exists(self, key: str) -> bool:
            raise AssertionError("exists must not run after authorization failure")

    denied = DeniedStorage(app.state.ctx.storage)
    service, db = _service(app, denied)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        assert row.owner_token is None
        assert "AuthorizationError" in (row.last_error or "")
        assert denied.delete_calls == 1
        assert denied.inner.exists(row.storage_key) is True
    finally:
        db.close()


def test_transient_s3_failure_is_retried_then_completes(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client, email="retry@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "retry.pdf", ["retry"]), auth["csrf"])

    class OnceTransient:
        def __init__(self, inner) -> None:
            self.inner = inner
            self.delete_calls = 0

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        def delete(self, key: str) -> None:
            self.delete_calls += 1
            if self.delete_calls == 1:
                raise TransientError("Object storage is temporarily unavailable.")
            self.inner.delete(key)

        def exists(self, key: str) -> bool:
            return self.inner.exists(key)

    flaky = OnceTransient(app.state.ctx.storage)
    service, db = _service(app, flaky)
    try:
        document = db.get(Document, doc_id)
        assert document is not None
        service.delete(document.owner, doc_id)
        row = db.query(StorageDeletion).filter_by(document_id=doc_id).one()
        assert row.status == "failed"
        row.next_attempt_at = utc_now()
        db.commit()
        result = service.retry_storage_deletions()
        db.refresh(row)
        assert result["deleted"] == 1
        assert row.status == "completed"
        assert row.owner_token is None
        assert flaky.delete_calls == 2
        assert flaky.exists(row.storage_key) is False
    finally:
        db.close()
