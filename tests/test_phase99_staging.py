from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from docuflow.staging_checks import (
    is_loopback_host,
    is_production_public_host,
    opt_in_flag,
    smoke_target_errors,
)


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


def _serve(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_opt_in_flag_rejects_ambiguous_values() -> None:
    assert opt_in_flag("STAGING_SMOKE_MUTATIONS", None) == (False, None)
    assert opt_in_flag("STAGING_SMOKE_MUTATIONS", "") == (False, None)
    assert opt_in_flag("STAGING_SMOKE_MUTATIONS", "0") == (False, None)
    assert opt_in_flag("STAGING_SMOKE_MUTATIONS", "1") == (True, None)
    enabled, error = opt_in_flag("STAGING_SMOKE_MUTATIONS", "true")
    assert enabled is False
    assert error is not None
    assert "must be unset, 0, or 1" in error


def test_smoke_target_rejects_production_and_requires_confirm() -> None:
    assert is_loopback_host("127.0.0.1") is True
    assert is_production_public_host("docuflow-api.onrender.com") is True
    assert is_production_public_host("docuflowai.site") is True
    assert is_production_public_host("www.docuflowai.online") is True
    assert is_production_public_host("docuflow-staging-api.onrender.com") is False
    assert smoke_target_errors("https://docuflow-api.onrender.com") != []
    assert any("production" in item for item in smoke_target_errors("https://docuflow-api.onrender.com"))
    assert any("production" in item for item in smoke_target_errors("https://docuflowai.site"))
    staging = "https://docuflow-staging-api.onrender.com"
    assert any("STAGING_HOST_CONFIRM" in item for item in smoke_target_errors(staging))
    assert smoke_target_errors(staging, "docuflow-staging-api.onrender.com") == []
    assert smoke_target_errors(staging, "other-host") != []
    assert smoke_target_errors("http://127.0.0.1:9") == []


def test_staging_smoke_refuses_production_hostname() -> None:
    result = _run(
        "scripts/staging_smoke.py",
        {
            "STAGING_API_URL": "https://docuflow-api.onrender.com",
            "STAGING_HOST_CONFIRM": "docuflow-api.onrender.com",
        },
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "production" in result.stdout.lower()
    assert "postgres://" not in result.stdout.lower()


def test_staging_smoke_refuses_production_custom_domain() -> None:
    result = _run(
        "scripts/staging_smoke.py",
        {
            "STAGING_API_URL": "https://docuflowai.site",
            "STAGING_HOST_CONFIRM": "docuflowai.site",
        },
    )
    assert result.returncode == 1
    assert "production" in result.stdout.lower()


def test_staging_smoke_requires_host_confirm_for_non_loopback() -> None:
    result = _run(
        "scripts/staging_smoke.py",
        {"STAGING_API_URL": "https://docuflow-staging-api.onrender.com"},
        unset=("STAGING_HOST_CONFIRM",),
    )
    assert result.returncode == 1
    assert "STAGING_HOST_CONFIRM" in result.stdout


def test_staging_smoke_ambiguous_mutations_flag_fails() -> None:
    server = _serve(_OkHandler)
    try:
        host, port = server.server_address[:2]
        result = _run(
            "scripts/staging_smoke.py",
            {
                "STAGING_API_URL": f"http://{host}:{port}",
                "STAGING_SMOKE_MUTATIONS": "true",
            },
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "STAGING_SMOKE_MUTATIONS" in result.stdout
    assert "PASS: authentication" not in result.stdout


def _recording_auth_handler(posts: list[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(_OkHandler):
        def do_POST(self) -> None:  # noqa: N802
            posts.append(self.path)
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                self.rfile.read(length)
            body = b'{"detail":"invalid credentials"}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def test_staging_smoke_register_requires_second_opt_in() -> None:
    posts: list[str] = []
    server = _serve(_recording_auth_handler(posts))
    try:
        host, port = server.server_address[:2]
        result = _run(
            "scripts/staging_smoke.py",
            {
                "STAGING_API_URL": f"http://{host}:{port}",
                "STAGING_SMOKE_MUTATIONS": "1",
                "STAGING_SMOKE_EMAIL": "probe@example.com",
                "STAGING_SMOKE_PASSWORD": "super-secret-1",
            },
            unset=("STAGING_SMOKE_REGISTER",),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL: authentication login" in result.stdout
    assert "/v1/auth/register" not in posts
    assert "/v1/auth/login" in posts
    assert "super-secret-1" not in result.stdout


def test_staging_smoke_mutations_are_skipped_without_opt_in() -> None:
    server = _serve(_OkHandler)
    try:
        host, port = server.server_address[:2]
        result = _run(
            "scripts/staging_smoke.py",
            {
                "STAGING_API_URL": f"http://{host}:{port}",
                "STAGING_SMOKE_EMAIL": "probe@example.com",
                "STAGING_SMOKE_PASSWORD": "super-secret-1",
                "STAGING_SMOKE_PDF": str(Path("README.md")),
                "STAGING_SMOKE_REGISTER": "1",
            },
            unset=("STAGING_SMOKE_MUTATIONS",),
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: GET /health" in result.stdout
    assert "STAGING_SMOKE_MUTATIONS is not 1" in result.stdout
    assert "PASS: authentication" not in result.stdout
    assert "super-secret-1" not in result.stdout


def test_staging_smoke_refuses_production_frontend_host() -> None:
    server = _serve(_OkHandler)
    try:
        host, port = server.server_address[:2]
        result = _run(
            "scripts/staging_smoke.py",
            {
                "STAGING_API_URL": f"http://{host}:{port}",
                "STAGING_WEB_URL": "https://docuflow-web.onrender.com",
            },
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 1
    assert "FAIL: frontend" in result.stdout
    assert "production" in result.stdout.lower()


def test_migrate_verify_rejects_incorrect_confirmation() -> None:
    result = _run(
        "scripts/staging_migrate_verify.py",
        {
            "STAGING_MIGRATE_VERIFY": "1",
            "DATABASE_URL": "postgresql://u:p@docuflow-staging-db/docuflow_staging",
            "STAGING_DATABASE_CONFIRM": "wrong-name",
        },
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "does not match" in result.stdout
    assert "postgres://" not in result.stdout.lower()


def test_provider_test_still_optional_without_credentials() -> None:
    text = Path("tests/test_phase95_readiness.py").read_text()
    assert "docuflow-test/" in text
    assert "is_forbidden_live_test_bucket" in text
    assert "@pytest.mark.provider" in text
