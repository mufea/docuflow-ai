from __future__ import annotations

import pytest
from pydantic import SecretStr

from docuflow.cleanup import (
    CleanupConfigError,
    parse_args,
    run_cleanup_cli,
    validate_cleanup_configuration,
)
from docuflow.config import Settings
from docuflow.jobs.retention import CleanupStats
from docuflow.jobs.scheduler import CleanupScheduler


def _staging_s3(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "production",
        "secret_key": "unique-staging-secret-key-32chars!!",
        "database_url": "postgresql+psycopg://u:p@docuflow-staging-db/docuflow_staging",
        "storage_backend": "s3",
        "s3_bucket": "docuflowai-staging",
        "s3_access_key_id": SecretStr("staging-key"),
        "s3_secret_access_key": SecretStr("staging-secret"),
        "job_broker": "inline",
        "public_api_url": "https://docuflow-staging-api.onrender.com",
        "public_web_url": "https://docuflow-staging-web.onrender.com",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _production_s3(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "production",
        "secret_key": "unique-production-secret-key-32ch!!",
        "database_url": "postgresql+psycopg://u:p@docuflow-db/docuflow",
        "storage_backend": "s3",
        "s3_bucket": "docuflowai-documents",
        "s3_access_key_id": SecretStr("prod-key"),
        "s3_secret_access_key": SecretStr("prod-secret"),
        "job_broker": "inline",
        "public_api_url": "https://docuflow-api.onrender.com",
        "public_web_url": "https://docuflow-web.onrender.com",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_parse_args_dry_run() -> None:
    assert parse_args([]).dry_run is False
    assert parse_args(["--dry-run"]).dry_run is True


def test_empty_bucket_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    errors = validate_cleanup_configuration(_staging_s3(s3_bucket=""))
    assert any("S3_BUCKET is required" in item for item in errors)


def test_staging_context_rejects_live_and_legacy_production_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER_SERVICE_NAME", "docuflow-staging-cleanup")
    live = validate_cleanup_configuration(_staging_s3(s3_bucket="docuflowai-documents"))
    assert any("production bucket" in item for item in live)
    legacy = validate_cleanup_configuration(_staging_s3(s3_bucket="docuflow-documents"))
    assert any("production bucket" in item for item in legacy)
    ok = validate_cleanup_configuration(_staging_s3())
    assert ok == []


def test_production_context_allows_production_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    assert validate_cleanup_configuration(_production_s3()) == []


def test_production_cron_service_name_allows_production_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER_SERVICE_NAME", "docuflow-cleanup")
    assert validate_cleanup_configuration(_production_s3()) == []


def test_missing_s3_keys_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    errors = validate_cleanup_configuration(_staging_s3(s3_access_key_id=None, s3_secret_access_key=None))
    assert any("S3_ACCESS_KEY_ID" in item for item in errors)


def test_unsafe_config_fails_before_any_factory() -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cleanup must not connect or mutate on unsafe config")

    with pytest.raises(CleanupConfigError) as caught:
        run_cleanup_cli(
            _staging_s3(s3_bucket=""),
            dry_run=False,
            run_cleanup=boom,  # type: ignore[arg-type]
            storage_factory=boom,  # type: ignore[arg-type]
            engine_factory=boom,  # type: ignore[arg-type]
        )
    assert any("S3_BUCKET is required" in item for item in caught.value.errors)


def test_dry_run_never_builds_storage_or_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    settings = _staging_s3()
    calls: list[str] = []

    class ForbiddenStorage:
        def delete(self, key: str) -> None:
            calls.append(f"delete:{key}")
            raise AssertionError("storage.delete must not run in dry-run")

    def storage_factory(_settings: Settings) -> ForbiddenStorage:
        calls.append("storage_factory")
        return ForbiddenStorage()

    def engine_factory(_settings: Settings) -> object:
        calls.append("engine_factory")
        raise AssertionError("engine must not be created in dry-run")

    def run_cleanup(*_args: object, **_kwargs: object) -> CleanupStats:
        calls.append("run_cleanup")
        raise AssertionError("run_runtime_cleanup must not run in dry-run")

    code = run_cleanup_cli(
        settings,
        dry_run=True,
        run_cleanup=run_cleanup,
        storage_factory=storage_factory,  # type: ignore[arg-type]
        engine_factory=engine_factory,  # type: ignore[arg-type]
    )
    assert code == 0
    assert calls == []


def test_dry_run_still_rejects_unsafe_config() -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry-run must not connect after unsafe config")

    with pytest.raises(CleanupConfigError):
        run_cleanup_cli(
            _staging_s3(s3_bucket="docuflowai-documents"),
            dry_run=True,
            run_cleanup=boom,  # type: ignore[arg-type]
            storage_factory=boom,  # type: ignore[arg-type]
            engine_factory=boom,  # type: ignore[arg-type]
        )


def test_mutating_path_invokes_cleanup_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    ran: list[str] = []

    class FakeEngine:
        def dispose(self) -> None:
            ran.append("dispose")

    class FakeSession:
        def close(self) -> None:
            ran.append("close")

    def engine_factory(_settings: Settings) -> FakeEngine:
        ran.append("engine")
        return FakeEngine()

    def open_session(_engine: FakeEngine) -> FakeSession:
        ran.append("session")
        return FakeSession()

    def storage_factory(_settings: Settings) -> object:
        ran.append("storage")
        return object()

    def run_cleanup(*_args: object, **_kwargs: object) -> CleanupStats:
        ran.append("cleanup")
        return CleanupStats()

    code = run_cleanup_cli(
        _staging_s3(),
        dry_run=False,
        run_cleanup=run_cleanup,
        storage_factory=storage_factory,  # type: ignore[arg-type]
        engine_factory=engine_factory,  # type: ignore[arg-type]
        open_session=open_session,  # type: ignore[arg-type]
    )
    assert code == 0
    assert ran == ["engine", "session", "storage", "cleanup", "close", "dispose"]


def test_scheduler_refuses_production_bucket_in_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER_SERVICE_NAME", "docuflow-staging-cleanup")
    opened = {"count": 0}

    class DummySession:
        def close(self) -> None:
            return None

    def factory() -> DummySession:
        opened["count"] += 1
        return DummySession()

    scheduler = CleanupScheduler(
        factory,  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        _staging_s3(s3_bucket="docuflowai-documents"),
    )
    scheduler.run_once()
    assert opened["count"] == 0
