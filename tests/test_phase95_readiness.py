from __future__ import annotations

import os
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, DocuflowError, NotFoundError, TransientError
from docuflow.staging_checks import is_forbidden_live_test_bucket
from docuflow.storage.s3 import S3Storage, classify_s3_client_error
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload
from tests.test_phase94_storage import _client_error, _s3


def test_ready_does_not_leak_dependency_errors(client: TestClient, app) -> None:
    class LeakyStorage:
        def ping(self) -> None:
            raise RuntimeError("postgres://user:supersecret@db/docuflow signed?X-Amz-Signature=abc traceback")

    app.state.ctx.storage = LeakyStorage()
    response = client.get("/ready")
    assert response.status_code == 503
    text = response.text
    assert "supersecret" not in text
    assert "postgres://" not in text
    assert "X-Amz-Signature" not in text
    assert "traceback" not in text.lower()
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["storage"] is False
    assert set(body.keys()) == {"status", "checks", "broker", "rq_workers"}
    assert set(body["checks"].keys()) == {"database", "redis", "storage"}


def test_cross_user_cannot_download_another_users_file(client: TestClient, tmp_path: Path) -> None:
    first = register_and_login(client, "owner-dl@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "private.pdf", ["secret page"]), first["csrf"])
    client.post("/v1/auth/logout")
    register_and_login(client, "other-dl@example.com")
    denied = client.get(f"/v1/documents/{doc_id}/download")
    assert denied.status_code == 403
    assert "X-Amz-Signature" not in denied.text


def test_signed_url_returns_provider_url_without_logging_it(monkeypatch, caplog) -> None:
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://example.invalid/obj?X-Amz-Signature=secret"
    storage = _s3(monkeypatch, client)
    caplog.set_level("WARNING", logger="docuflow.storage")
    url = storage.signed_url("user/object.bin", expires_seconds=60, filename="file.pdf")
    assert url == "https://example.invalid/obj?X-Amz-Signature=secret"
    client.generate_presigned_url.assert_called_once()
    assert "X-Amz-Signature" not in caplog.text
    assert "signed?" not in caplog.text


def test_signed_url_client_error_returns_none_without_secrets(monkeypatch, caplog) -> None:
    client = MagicMock()
    client.generate_presigned_url.side_effect = _client_error(
        "AccessDenied", 403, message="https://example.invalid/signed?X-Amz-Signature=abc"
    )
    storage = _s3(monkeypatch, client)
    caplog.set_level("WARNING", logger="docuflow.storage")
    assert storage.signed_url("user/denied.bin", expires_seconds=30) is None
    assert "X-Amz-Signature" not in caplog.text
    assert "AKIA" not in caplog.text


def test_invalid_access_key_is_authorization(monkeypatch) -> None:
    kind, code, status = classify_s3_client_error(_client_error("InvalidAccessKeyId", 403))
    assert kind == "authorization"
    assert code == "InvalidAccessKeyId"
    assert status == 403
    client = MagicMock()
    client.delete_object.side_effect = _client_error("InvalidAccessKeyId", 403, message="AKIAEXAMPLE")
    storage = _s3(monkeypatch, client)
    try:
        storage.delete("user/secret.bin")
        raise AssertionError("InvalidAccessKeyId must raise AuthorizationError")
    except AuthorizationError as exc:
        assert "AKIA" not in str(exc)


def test_upload_put_calls_s3_and_exists_true(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "in.bin"
    source.write_bytes(b"%PDF-1.4 mock")
    client = MagicMock()
    storage = _s3(monkeypatch, client)
    stored = storage.put("user/in.bin", source, "application/pdf")
    assert stored.key == "user/in.bin"
    client.upload_file.assert_called_once()
    client.head_object.return_value = {}
    assert storage.exists("user/in.bin") is True


@pytest.mark.provider
def test_optional_live_s3_provider_roundtrip(tmp_path: Path) -> None:
    bucket = os.environ.get("TEST_S3_BUCKET", "").strip()
    access = os.environ.get("TEST_S3_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("TEST_S3_SECRET_ACCESS_KEY", "").strip()
    if not bucket or not access or not secret:
        pytest.skip(
            "live S3-compatible credentials not configured "
            "(TEST_S3_BUCKET / TEST_S3_ACCESS_KEY_ID / TEST_S3_SECRET_ACCESS_KEY)"
        )
    if is_forbidden_live_test_bucket(bucket, production_bucket=os.environ.get("PRODUCTION_S3_BUCKET", "")):
        pytest.fail("TEST_S3_BUCKET looks like a production bucket. Use a dedicated test bucket.")

    prefix = f"docuflow-test/{uuid.uuid4().hex}/"
    key = f"{prefix}probe.bin"
    source = tmp_path / "probe.bin"
    payload = b"docuflow-test-probe"
    source.write_bytes(payload)
    dest = tmp_path / "downloaded.bin"
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        storage_backend="s3",
        s3_bucket=bucket,
        s3_access_key_id=SecretStr(access),
        s3_secret_access_key=SecretStr(secret),
        s3_endpoint_url=os.environ.get("TEST_S3_ENDPOINT_URL") or None,
        s3_region=os.environ.get("TEST_S3_REGION", "auto"),
    )
    storage = S3Storage(settings)
    try:
        storage.put(key, source, "application/octet-stream")
        assert storage.exists(key) is True
        storage.download(key, dest)
        assert dest.read_bytes() == payload
        signed = storage.signed_url(key, expires_seconds=60)
        assert signed is not None
        assert signed.startswith("http")
        parsed = urllib.parse.urlparse(signed)
        assert parsed.scheme in {"http", "https"} and parsed.netloc
        request = urllib.request.Request(signed, method="GET")  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                downloaded = response.read()
        except Exception:
            raise AssertionError("presigned GET failed") from None
        assert downloaded == payload
        storage.delete(key)
        assert storage.exists(key) is False
    finally:
        try:
            storage.delete(key)
        except (AuthorizationError, NotFoundError, TransientError, DocuflowError):
            pass
