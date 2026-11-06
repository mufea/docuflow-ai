#!/usr/bin/env python3
"""Staging HTTP smoke checks. Does not deploy or migrate.

Requires STAGING_API_URL. Exits 2 with NOT EXECUTED when unset so CI stays green.
Never prints secrets, DSNs, or signed URLs.

Statuses: PASS, FAIL, SKIPPED, NOT EXECUTED.
Skipped extended checks are never reported as successful.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from docuflow.staging_checks import (
    contains_secret_fragment,
    emit,
    exit_code,
    http_url_is_valid,
    is_production_public_host,
    opt_in_flag,
    smoke_target_errors,
)

DEFAULT_TIMEOUT_SECONDS = 30


def _mutations_enabled() -> bool:
    return os.environ.get("STAGING_SMOKE_MUTATIONS", "").strip() == "1"


def _register_enabled() -> bool:
    return os.environ.get("STAGING_SMOKE_REGISTER", "").strip() == "1"


def _timeout() -> float:
    raw = os.environ.get("STAGING_SMOKE_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _reject_secrets(payload: str, name: str) -> bool:
    if contains_secret_fragment(payload):
        emit("FAIL", name, "response contained a secret-like fragment")
        return False
    return True


def _json_body(response: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _csrf_headers(client: httpx.Client, origin: str) -> dict[str, str]:
    headers = {"X-CSRF-Token": client.cookies.get("df_csrf") or ""}
    if origin:
        headers["Origin"] = origin.rstrip("/")
    return headers


def _basic_checks(client: httpx.Client, base: str, statuses: list[str]) -> None:
    try:
        health = client.get(f"{base}/health")
    except httpx.HTTPError:
        emit("FAIL", "GET /health", "network error or timeout")
        statuses.append("FAIL")
        return
    health_text = health.text
    if not _reject_secrets(health_text, "GET /health"):
        statuses.append("FAIL")
        return
    body = _json_body(health)
    if health.status_code != 200 or not body or body.get("status") != "ok":
        status_value = body.get("status") if body else "invalid-json"
        emit("FAIL", "GET /health", f"HTTP {health.status_code} status={status_value}")
        statuses.append("FAIL")
    else:
        emit("PASS", "GET /health", f"HTTP {health.status_code} status=ok")
        statuses.append("PASS")
        if body.get("service") != "docuflow-api":
            emit("FAIL", "GET /health service", "missing service=docuflow-api")
            statuses.append("FAIL")
        else:
            emit("PASS", "GET /health service", "service=docuflow-api")
            statuses.append("PASS")

    try:
        ready = client.get(f"{base}/ready")
    except httpx.HTTPError:
        emit("FAIL", "GET /ready", "network error or timeout")
        statuses.append("FAIL")
        return
    ready_text = ready.text
    if not _reject_secrets(ready_text, "GET /ready"):
        statuses.append("FAIL")
        return
    ready_body = _json_body(ready)
    if ready.status_code == 200 and ready_body and ready_body.get("status") == "ready":
        emit("PASS", "GET /ready", f"HTTP 200 broker={ready_body.get('broker')} checks={ready_body.get('checks')}")
        statuses.append("PASS")
        if ready_body.get("broker") != "inline":
            emit("FAIL", "GET /ready broker", "staging must use JOB_BROKER=inline")
            statuses.append("FAIL")
        else:
            emit("PASS", "GET /ready broker", "inline")
            statuses.append("PASS")
    elif ready.status_code == 503:
        emit("FAIL", "GET /ready", "HTTP 503 degraded")
        statuses.append("FAIL")
    else:
        emit("FAIL", "GET /ready", f"HTTP {ready.status_code} unexpected")
        statuses.append("FAIL")


def _extended_auth(client: httpx.Client, base: str, statuses: list[str]) -> bool:
    email = os.environ.get("STAGING_SMOKE_EMAIL", "").strip()
    password = os.environ.get("STAGING_SMOKE_PASSWORD", "").strip()
    if not email or not password:
        emit("SKIPPED", "authentication", "STAGING_SMOKE_EMAIL / STAGING_SMOKE_PASSWORD unset")
        statuses.append("SKIPPED")
        return False
    login = client.post(f"{base}/v1/auth/login", json={"email": email, "password": password})
    if login.status_code != 200 and _register_enabled():
        name = os.environ.get("STAGING_SMOKE_NAME", "Staging Probe").strip() or "Staging Probe"
        register = client.post(
            f"{base}/v1/auth/register",
            json={"email": email, "password": password, "name": name},
        )
        if register.status_code not in {200, 201}:
            emit("FAIL", "authentication register", f"HTTP {register.status_code}")
            statuses.append("FAIL")
            return False
        login = client.post(f"{base}/v1/auth/login", json={"email": email, "password": password})
    if login.status_code != 200:
        emit("FAIL", "authentication login", f"HTTP {login.status_code}")
        statuses.append("FAIL")
        return False
    if not _reject_secrets(login.text, "authentication login"):
        statuses.append("FAIL")
        return False
    me = client.get(f"{base}/v1/auth/me")
    if me.status_code != 200:
        emit("FAIL", "authentication me", f"HTTP {me.status_code}")
        statuses.append("FAIL")
        return False
    emit("PASS", "authentication", "login and /v1/auth/me succeeded")
    statuses.append("PASS")
    return True


def _extended_documents(
    client: httpx.Client,
    base: str,
    origin: str,
    statuses: list[str],
) -> str | None:
    pdf = os.environ.get("STAGING_SMOKE_PDF", "").strip()
    if not pdf:
        emit("SKIPPED", "document_upload", "STAGING_SMOKE_PDF unset")
        statuses.append("SKIPPED")
        return None
    path = Path(pdf)
    if not path.is_file():
        emit("FAIL", "document_upload", "STAGING_SMOKE_PDF is not a file")
        statuses.append("FAIL")
        return None
    with path.open("rb") as handle:
        uploaded = client.post(
            f"{base}/v1/documents",
            files={"file": (path.name, handle, "application/pdf")},
            headers=_csrf_headers(client, origin),
        )
    if uploaded.status_code != 200:
        emit("FAIL", "document_upload", f"HTTP {uploaded.status_code}")
        statuses.append("FAIL")
        return None
    if not _reject_secrets(uploaded.text, "document_upload"):
        statuses.append("FAIL")
        return None
    doc_id = str(uploaded.json().get("id") or "")
    if not doc_id:
        emit("FAIL", "document_upload", "response missing document id")
        statuses.append("FAIL")
        return None
    emit("PASS", "document_upload", "upload accepted")
    statuses.append("PASS")
    return doc_id


def _wait_job(client: httpx.Client, base: str, job_id: str, timeout: float) -> dict[str, Any] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"{base}/v1/jobs/{job_id}")
        if not _reject_secrets(response.text, "job_status"):
            return None
        payload = _json_body(response) or {}
        if payload.get("status") in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.5)
    return None


def _extended_job(client: httpx.Client, base: str, origin: str, doc_id: str, statuses: list[str]) -> None:
    created = client.post(
        f"{base}/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers=_csrf_headers(client, origin),
    )
    if created.status_code != 200:
        emit("FAIL", "document_processing", f"HTTP {created.status_code}")
        statuses.append("FAIL")
        return
    job_id = str((created.json() or {}).get("id") or "")
    job = _wait_job(client, base, job_id, _timeout()) if job_id else None
    if not job:
        emit("FAIL", "document_processing", "job did not reach a terminal status")
        statuses.append("FAIL")
        return
    if job.get("status") != "completed":
        emit("FAIL", "document_processing", f"status={job.get('status')}")
        statuses.append("FAIL")
        return
    emit("PASS", "document_processing", "extract_text completed")
    statuses.append("PASS")


def _extended_download(client: httpx.Client, base: str, doc_id: str, statuses: list[str]) -> None:
    response = client.get(f"{base}/v1/documents/{doc_id}/download")
    if response.status_code not in {301, 302, 303, 307, 308} and contains_secret_fragment(response.text):
        emit("FAIL", "document_download", "response contained a secret-like fragment")
        statuses.append("FAIL")
        return
    if response.status_code in {200, 302}:
        emit("PASS", "document_download", f"HTTP {response.status_code}")
        statuses.append("PASS")
    else:
        emit("FAIL", "document_download", f"HTTP {response.status_code}")
        statuses.append("FAIL")


def _extended_cross_user(base: str, doc_id: str, statuses: list[str]) -> None:
    email = os.environ.get("STAGING_SMOKE_SECOND_EMAIL", "").strip()
    password = os.environ.get("STAGING_SMOKE_SECOND_PASSWORD", "").strip()
    if not email or not password:
        emit("SKIPPED", "cross_user_access", "STAGING_SMOKE_SECOND_EMAIL / STAGING_SMOKE_SECOND_PASSWORD unset")
        statuses.append("SKIPPED")
        return
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=False) as other:
            login = other.post(f"{base}/v1/auth/login", json={"email": email, "password": password})
            if login.status_code != 200:
                emit("FAIL", "cross_user_access", f"second login HTTP {login.status_code}")
                statuses.append("FAIL")
                return
            denied = other.get(f"{base}/v1/documents/{doc_id}/download")
    except httpx.HTTPError:
        emit("FAIL", "cross_user_access", "network error or timeout")
        statuses.append("FAIL")
        return
    if denied.status_code == 403:
        emit("PASS", "cross_user_access", "HTTP 403")
        statuses.append("PASS")
    else:
        emit("FAIL", "cross_user_access", f"HTTP {denied.status_code}")
        statuses.append("FAIL")


def _extended_delete(client: httpx.Client, base: str, origin: str, doc_id: str, statuses: list[str]) -> bool:
    deleted = client.delete(f"{base}/v1/documents/{doc_id}", headers=_csrf_headers(client, origin))
    if deleted.status_code in {200, 204}:
        emit("PASS", "storage_deletion", f"HTTP {deleted.status_code}")
        statuses.append("PASS")
        return True
    emit("FAIL", "storage_deletion", f"HTTP {deleted.status_code}")
    statuses.append("FAIL")
    return False


def _frontend_check(statuses: list[str]) -> None:
    web = os.environ.get("STAGING_WEB_URL", "").strip().rstrip("/")
    if not web:
        emit("SKIPPED", "frontend", "STAGING_WEB_URL unset")
        statuses.append("SKIPPED")
        return
    if not http_url_is_valid(web):
        emit("FAIL", "frontend", "STAGING_WEB_URL must be http:// or https://")
        statuses.append("FAIL")
        return
    web_host = urlparse(web).hostname or ""
    if is_production_public_host(web_host):
        emit("FAIL", "frontend", "STAGING_WEB_URL points at a production web host")
        statuses.append("FAIL")
        return
    try:
        response = httpx.get(web, timeout=_timeout(), follow_redirects=True)
    except httpx.HTTPError:
        emit("FAIL", "frontend", "network error or timeout")
        statuses.append("FAIL")
        return
    if contains_secret_fragment(response.text):
        emit("FAIL", "frontend", "response contained a secret-like fragment")
        statuses.append("FAIL")
        return
    if response.status_code == 200:
        emit("PASS", "frontend", "HTTP 200")
        statuses.append("PASS")
    else:
        emit("FAIL", "frontend", f"HTTP {response.status_code}")
        statuses.append("FAIL")


def _skip_extended(statuses: list[str], reason: str) -> None:
    for name in (
        "authentication",
        "document_upload",
        "document_processing",
        "document_download",
        "cross_user_access",
        "storage_deletion",
    ):
        emit("SKIPPED", name, reason)
        statuses.append("SKIPPED")


def _best_effort_delete(client: httpx.Client, base: str, origin: str, doc_id: str) -> None:
    try:
        client.delete(f"{base}/v1/documents/{doc_id}", headers=_csrf_headers(client, origin))
    except httpx.HTTPError:
        return


def main() -> int:
    base = os.environ.get("STAGING_API_URL", "").strip().rstrip("/")
    if not base:
        emit("NOT EXECUTED", "staging_smoke", "STAGING_API_URL is not set. No staging environment was contacted.")
        return 2
    host_errors = smoke_target_errors(base, os.environ.get("STAGING_HOST_CONFIRM", ""))
    if host_errors:
        for item in host_errors:
            emit("FAIL", "staging_api_url", item)
        return 1
    for flag in ("STAGING_SMOKE_MUTATIONS", "STAGING_SMOKE_REGISTER"):
        _enabled, flag_error = opt_in_flag(flag, os.environ.get(flag))
        if flag_error:
            emit("FAIL", "staging_smoke_config", flag_error)
            return 1

    statuses: list[str] = []
    origin = os.environ.get("STAGING_WEB_URL", "").strip()
    with httpx.Client(timeout=_timeout(), follow_redirects=False) as client:
        _basic_checks(client, base, statuses)
        doc_id: str | None = None
        deleted = False
        try:
            if "FAIL" in statuses:
                _skip_extended(statuses, "basic checks failed")
            elif not _mutations_enabled():
                _skip_extended(statuses, "STAGING_SMOKE_MUTATIONS is not 1")
            else:
                authenticated = _extended_auth(client, base, statuses)
                doc_id = _extended_documents(client, base, origin, statuses) if authenticated else None
                if not authenticated:
                    emit("SKIPPED", "document_upload", "authentication did not run")
                    emit("SKIPPED", "document_processing", "authentication did not run")
                    emit("SKIPPED", "document_download", "authentication did not run")
                    emit("SKIPPED", "cross_user_access", "authentication did not run")
                    emit("SKIPPED", "storage_deletion", "authentication did not run")
                    statuses.extend(["SKIPPED"] * 5)
                elif doc_id:
                    _extended_job(client, base, origin, doc_id, statuses)
                    _extended_download(client, base, doc_id, statuses)
                    _extended_cross_user(base, doc_id, statuses)
                    deleted = _extended_delete(client, base, origin, doc_id, statuses)
                else:
                    emit("SKIPPED", "document_processing", "no uploaded document")
                    emit("SKIPPED", "document_download", "no uploaded document")
                    emit("SKIPPED", "cross_user_access", "no uploaded document")
                    emit("SKIPPED", "storage_deletion", "no uploaded document")
                    statuses.extend(["SKIPPED"] * 4)
        finally:
            if doc_id and not deleted:
                _best_effort_delete(client, base, origin, doc_id)
    _frontend_check(statuses)
    return exit_code(statuses)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
