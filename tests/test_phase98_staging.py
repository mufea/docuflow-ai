from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.jobs.recovery import QUEUED_RECOVERY_LIMIT
from docuflow.staging_checks import (
    audit_staging_blueprint,
    confirm_matches,
    contains_secret_fragment,
    database_identity,
    expected_schema_gaps,
    identity_label,
    is_forbidden_live_test_bucket,
    is_production_bucket,
    is_production_database,
    is_production_public_host,
    sanitize_text,
    validate_staging_configuration,
)


def _active(path: str) -> str:
    lines = []
    for line in Path(path).read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _run(
    script: str,
    extra: dict[str, str] | None = None,
    *,
    unset: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in unset:
        env.pop(key, None)
    if extra:
        env.update(extra)
    return subprocess.run(  # noqa: S603
        [sys.executable, script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _staging_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "production",
        "secret_key": "unique-staging-secret-key-32chars!!",
        "database_url": "postgresql+psycopg://u:p@docuflow-staging-db/docuflow_staging",
        "storage_backend": "s3",
        "s3_bucket": "docuflow-staging",
        "s3_access_key_id": SecretStr("staging-key"),
        "s3_secret_access_key": SecretStr("staging-secret"),
        "job_broker": "inline",
        "ai_provider": "mock",
        "email_backend": "console",
        "cookie_secure": True,
        "public_api_url": "https://docuflow-staging-api.onrender.com",
        "public_web_url": "https://docuflow-staging-web.onrender.com",
        "cors_origins": "https://docuflow-staging-web.onrender.com",
        "trusted_hosts": ".onrender.com",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = b'{"status":"ok","service":"docuflow-api"}'
            code = 200
        elif self.path == "/ready":
            body = (
                b'{"status":"ready","checks":{"database":true,"redis":true,"storage":true},'
                b'"broker":"inline","rq_workers":0}'
            )
            code = 200
        else:
            body = b"{}"
            code = 404
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class _DegradedHandler(_OkHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/ready":
            body = (
                b'{"status":"degraded","checks":{"database":false,"redis":true,"storage":true},'
                b'"broker":"inline","rq_workers":0}'
            )
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


class _SecretHandler(_OkHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = b'{"status":"ok","service":"docuflow-api","dsn":"postgres://user:supersecret@db/docuflow"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def _serve(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_staging_blueprint_omits_redis_and_keeps_inline() -> None:
    text = Path("infra/render.staging.yaml").read_text()
    issues = audit_staging_blueprint(text)
    assert issues.errors == []
    active = _active("infra/render.staging.yaml")
    assert "type: redis" not in active
    assert "REDIS_URL" not in active
    assert "docuflow-staging-redis" not in active
    assert "value: inline" in active
    assert "type: worker" not in active
    assert "name: docuflow-staging-api" in active
    assert "name: docuflow-staging-db" in active
    assert "python -m docuflow.migrate" in active
    assert "healthCheckPath: /health" in text


def test_production_blueprint_still_has_optional_redis() -> None:
    active = _active("infra/render.yaml")
    assert "name: docuflow-redis" in active
    assert "name: docuflow-api" in active
    assert "value: inline" in active
    assert "type: worker" not in active
    assert "name: docuflow-staging-api" not in active


def test_queued_recovery_limit_unchanged() -> None:
    assert QUEUED_RECOVERY_LIMIT == 100


def test_sanitize_and_identity_never_include_secrets() -> None:
    raw = "postgres://user:supersecret@db/docuflow?password=supersecret"
    host, name = database_identity(raw)
    label = identity_label(host, name)
    assert "supersecret" not in label
    assert "postgres://" not in label
    sanitized = sanitize_text(raw)
    assert "supersecret" not in sanitized
    assert contains_secret_fragment(raw) is True


def test_production_resource_reuse_is_detected() -> None:
    assert is_production_database("docuflow-db", "docuflow") is True
    assert is_production_database("docuflow-staging-db", "docuflow_staging") is False
    assert is_production_database("db.internal", "app", production_host="db.internal") is True
    assert is_production_bucket("docuflow-documents") is True
    assert is_production_bucket("docuflow-staging") is False
    assert is_production_bucket("company", production_bucket="company") is True
    assert is_forbidden_live_test_bucket("docuflow-documents") is True
    assert is_forbidden_live_test_bucket("docuflow-test") is False
    assert is_production_public_host("docuflow-api.onrender.com") is True
    assert is_production_public_host("docuflow-staging-api.onrender.com") is False
    assert confirm_matches("dbhost", "stagingdb", "stagingdb") is True
    assert confirm_matches("dbhost", "stagingdb", "dbhost/stagingdb") is True
    assert confirm_matches("dbhost", "stagingdb", "other") is False


def test_staging_config_rejects_production_reuse_and_rq() -> None:
    ok = validate_staging_configuration(_staging_settings())
    assert ok.errors == []
    reused_db = validate_staging_configuration(
        _staging_settings(database_url="postgresql+psycopg://u:p@docuflow-db/docuflow")
    )
    assert any("production database" in item for item in reused_db.errors)
    reused_bucket = validate_staging_configuration(_staging_settings(s3_bucket="docuflow-documents"))
    assert any("production bucket" in item for item in reused_bucket.errors)
    rq = validate_staging_configuration(_staging_settings(job_broker="rq", redis_url="redis://127.0.0.1:6379/0"))
    assert any("inline" in item for item in rq.errors)
    sqlite = validate_staging_configuration(_staging_settings(database_url="sqlite+pysqlite:///./data/x.db"))
    assert any("PostgreSQL" in item for item in sqlite.errors)


def test_expected_schema_gaps_detect_missing_0003_fields() -> None:
    gaps = expected_schema_gaps(
        {"cleanup_leases": {"name", "token", "locked_until"}},
        {"storage_deletions": set()},
    )
    assert any("acquired_at" in item for item in gaps)
    assert any("ix_storage_deletions_lease_until" in item for item in gaps)


def test_preflight_not_executed_without_flag() -> None:
    result = _run("scripts/staging_preflight.py", unset=("STAGING_PREFLIGHT",))
    assert result.returncode == 2
    assert "NOT EXECUTED" in result.stdout
    assert "postgres://" not in result.stdout.lower()


def test_preflight_fails_on_sqlite_and_keeps_secrets_out() -> None:
    result = _run(
        "scripts/staging_preflight.py",
        {
            "STAGING_PREFLIGHT": "1",
            "DOCUFLOW_ENV": "production",
            "DOCUFLOW_SECRET_KEY": "unique-staging-secret-key-32chars!!",
            "DATABASE_URL": "sqlite+pysqlite:///./data/nope.db",
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": "docuflow-staging",
            "S3_ACCESS_KEY_ID": "staging-key",
            "S3_SECRET_ACCESS_KEY": "staging-secret",
            "JOB_BROKER": "inline",
            "AI_PROVIDER": "mock",
            "EMAIL_BACKEND": "console",
            "DOCUFLOW_PUBLIC_API_URL": "https://docuflow-staging-api.onrender.com",
            "DOCUFLOW_PUBLIC_WEB_URL": "https://docuflow-staging-web.onrender.com",
            "DOCUFLOW_CORS_ORIGINS": "https://docuflow-staging-web.onrender.com",
        },
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "staging-secret" not in result.stdout
    assert "sqlite+pysqlite" not in result.stdout.lower() or "PostgreSQL" in result.stdout


def test_migrate_verify_not_executed_without_flag() -> None:
    result = _run("scripts/staging_migrate_verify.py", unset=("STAGING_MIGRATE_VERIFY",))
    assert result.returncode == 2
    assert "NOT EXECUTED" in result.stdout


def test_migrate_verify_refuses_production_identity_without_connecting() -> None:
    result = _run(
        "scripts/staging_migrate_verify.py",
        {
            "STAGING_MIGRATE_VERIFY": "1",
            "DATABASE_URL": "postgresql://owner:supersecret@docuflow-db/docuflow",
            "STAGING_DATABASE_CONFIRM": "docuflow",
        },
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "supersecret" not in result.stdout
    assert "postgres://" not in result.stdout.lower()


def test_migrate_verify_requires_confirm_and_refuses_sqlite() -> None:
    missing = _run(
        "scripts/staging_migrate_verify.py",
        {
            "STAGING_MIGRATE_VERIFY": "1",
            "DATABASE_URL": "postgresql://u:p@docuflow-staging-db/docuflow_staging",
        },
        unset=("STAGING_DATABASE_CONFIRM",),
    )
    assert missing.returncode == 1
    assert "STAGING_DATABASE_CONFIRM" in missing.stdout
    sqlite = _run(
        "scripts/staging_migrate_verify.py",
        {
            "STAGING_MIGRATE_VERIFY": "1",
            "DATABASE_URL": "sqlite+pysqlite:///./data/nope.db",
            "STAGING_DATABASE_CONFIRM": "nope.db",
        },
    )
    assert sqlite.returncode == 1
    assert "PostgreSQL" in sqlite.stdout


def test_staging_smoke_not_executed_without_url() -> None:
    result = _run("scripts/staging_smoke.py", unset=("STAGING_API_URL",))
    assert result.returncode == 2
    assert "NOT EXECUTED" in result.stdout
    assert "postgres://" not in result.stdout.lower()


def test_staging_smoke_rejects_invalid_url() -> None:
    result = _run("scripts/staging_smoke.py", {"STAGING_API_URL": "ftp://example.invalid"})
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_staging_smoke_pass_and_skips_extended_against_local_server() -> None:
    server = _serve(_OkHandler)
    try:
        host, port = server.server_address[:2]
        result = _run(
            "scripts/staging_smoke.py",
            {
                "STAGING_API_URL": f"http://{host}:{port}",
            },
            unset=("STAGING_SMOKE_EMAIL", "STAGING_SMOKE_PASSWORD", "STAGING_SMOKE_PDF", "STAGING_WEB_URL"),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: GET /health" in result.stdout
    assert "PASS: GET /ready" in result.stdout
    assert "SKIPPED: authentication" in result.stdout
    assert "SKIPPED" in result.stdout
    assert "PASS: authentication" not in result.stdout


def test_staging_smoke_ready_503_is_fail() -> None:
    server = _serve(_DegradedHandler)
    try:
        host, port = server.server_address[:2]
        result = _run("scripts/staging_smoke.py", {"STAGING_API_URL": f"http://{host}:{port}"})
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 1
    assert "FAIL: GET /ready" in result.stdout


def test_staging_smoke_secret_fragment_is_fail_and_redacted() -> None:
    server = _serve(_SecretHandler)
    try:
        host, port = server.server_address[:2]
        result = _run("scripts/staging_smoke.py", {"STAGING_API_URL": f"http://{host}:{port}"})
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "supersecret" not in result.stdout
    assert "postgres://" not in result.stdout.lower()
