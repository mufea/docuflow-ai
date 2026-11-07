#!/usr/bin/env python3
"""Owner-run production Gates 1-3. Prints HTTP status labels only.

Does not import docuflow. Does not print passwords, cookies, emails,
document ids, job payloads, or signed URL Location headers.

Allowed API host: docuflowai.site only.
Refuse STAGING_* mix-up. Require PRODUCTION_SMOKE_MUTATIONS=1 and
PRODUCTION_HOST_CONFIRM=docuflowai.site.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

ALLOWED_API = "https://docuflowai.site"
ALLOWED_HOST = "docuflowai.site"
ALLOWED_ORIGIN = "https://docuflowai.online"
TIMEOUT = 90.0
JOB_WAIT = 60.0


def emit(label: str, value: object) -> None:
    print(f"{label} {value}", flush=True)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _fail_config(message: str) -> int:
    emit("CONFIG_FAIL", message)
    return 2


def _csrf(client: httpx.Client) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("df_csrf") or "",
        "Origin": ALLOWED_ORIGIN,
    }


def _json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _login(client: httpx.Client, email: str, password: str) -> int:
    return client.post(
        f"{ALLOWED_API}/v1/auth/login",
        json={"email": email, "password": password},
    ).status_code


def _wait_job(client: httpx.Client, job_id: str) -> dict:
    deadline = time.time() + JOB_WAIT
    last: dict = {}
    while time.time() < deadline:
        response = client.get(f"{ALLOWED_API}/v1/jobs/{job_id}")
        last = _json(response)
        last["_http"] = response.status_code
        if last.get("status") in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.5)
    last["_http"] = last.get("_http", 0)
    last["status"] = last.get("status") or "timeout"
    return last


def main() -> int:
    if os.environ.get("STAGING_API_URL", "").strip():
        return _fail_config("unset STAGING_API_URL; this script is production-only")
    if os.environ.get("PRODUCTION_SMOKE_MUTATIONS", "").strip() != "1":
        return _fail_config("set PRODUCTION_SMOKE_MUTATIONS=1")
    confirm = os.environ.get("PRODUCTION_HOST_CONFIRM", "").strip().lower()
    if confirm != ALLOWED_HOST:
        return _fail_config("PRODUCTION_HOST_CONFIRM must be docuflowai.site")
    api = os.environ.get("PRODUCTION_API_URL", ALLOWED_API).strip().rstrip("/")
    if api != ALLOWED_API or _host(api) != ALLOWED_HOST:
        return _fail_config("PRODUCTION_API_URL must be https://docuflowai.site")

    email_a = os.environ.get("PRODUCTION_TEST_A_EMAIL", "").strip()
    pass_a = os.environ.get("PRODUCTION_TEST_A_PASSWORD", "").strip()
    email_b = os.environ.get("PRODUCTION_TEST_B_EMAIL", "").strip()
    pass_b = os.environ.get("PRODUCTION_TEST_B_PASSWORD", "").strip()
    pdf = os.environ.get("PRODUCTION_SMOKE_PDF", "").strip()
    if not email_a or not pass_a or not email_b or not pass_b:
        return _fail_config("set PRODUCTION_TEST_A/B EMAIL and PASSWORD")
    if email_a.lower() == email_b.lower():
        return _fail_config("A and B must be distinct accounts")
    path = Path(pdf)
    if not path.is_file():
        return _fail_config("PRODUCTION_SMOKE_PDF is not a file")

    doc_id = ""
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as a, httpx.Client(
        timeout=TIMEOUT, follow_redirects=False
    ) as b:
        emit(
            "A_invalid_login",
            a.post(
                f"{ALLOWED_API}/v1/auth/login",
                json={"email": email_a, "password": "not-the-password-used-for-this-test"},
            ).status_code,
        )
        emit("A_login", _login(a, email_a, pass_a))
        emit("A_me", a.get(f"{ALLOWED_API}/v1/auth/me").status_code)
        emit("B_login", _login(b, email_b, pass_b))
        emit("B_me", b.get(f"{ALLOWED_API}/v1/auth/me").status_code)
        emit("A_logout", a.post(f"{ALLOWED_API}/v1/auth/logout").status_code)
        emit("A_me_after_logout", a.get(f"{ALLOWED_API}/v1/auth/me").status_code)
        emit("A_login2", _login(a, email_a, pass_a))

        with path.open("rb") as handle:
            uploaded = a.post(
                f"{ALLOWED_API}/v1/documents",
                files={"file": (path.name, handle, "application/pdf")},
                headers=_csrf(a),
            )
        emit("A_upload", uploaded.status_code)
        doc_id = str(_json(uploaded).get("id") or "")
        emit("A_upload_id", "SET" if doc_id else "MISSING")

        spoof = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            spoof.write(b"not a pdf")
            spoof.close()
            with open(spoof.name, "rb") as handle:
                rejected = a.post(
                    f"{ALLOWED_API}/v1/documents",
                    files={"file": ("notes.pdf", handle, "application/pdf")},
                    headers=_csrf(a),
                )
            emit("A_upload_spoof", rejected.status_code)
        finally:
            Path(spoof.name).unlink(missing_ok=True)

        if not doc_id:
            return 1

        created = a.post(
            f"{ALLOWED_API}/v1/jobs",
            json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
            headers=_csrf(a),
        )
        emit("A_extract_create", created.status_code)
        job_id = str(_json(created).get("id") or "")
        job = _wait_job(a, job_id) if job_id else {"status": "missing", "_http": 0}
        emit("A_extract_http", job.get("_http"))
        emit("A_extract_status", job.get("status"))
        text = (job.get("result_payload") or {}).get("text") if isinstance(job.get("result_payload"), dict) else None
        emit("A_extract_text", "present" if text else "missing")

        download = a.get(f"{ALLOWED_API}/v1/documents/{doc_id}/download")
        emit("A_download", download.status_code)

        listed = b.get(f"{ALLOWED_API}/v1/documents")
        ids = []
        try:
            rows = listed.json()
            if isinstance(rows, list):
                ids = [str(item.get("id") or "") for item in rows if isinstance(item, dict)]
        except json.JSONDecodeError:
            ids = []
        emit("B_list", listed.status_code)
        emit("B_list_has_A_doc", "yes" if doc_id in ids else "no")
        emit("B_GET", b.get(f"{ALLOWED_API}/v1/documents/{doc_id}").status_code)
        emit("B_download", b.get(f"{ALLOWED_API}/v1/documents/{doc_id}/download").status_code)
        emit(
            "B_DELETE",
            b.delete(f"{ALLOWED_API}/v1/documents/{doc_id}", headers=_csrf(b)).status_code,
        )
        unauth = httpx.get(f"{ALLOWED_API}/v1/documents/{doc_id}", timeout=TIMEOUT, follow_redirects=False)
        emit("unauth_GET", unauth.status_code)

        emit("A_DELETE", a.delete(f"{ALLOWED_API}/v1/documents/{doc_id}", headers=_csrf(a)).status_code)
        emit("A_GET_after", a.get(f"{ALLOWED_API}/v1/documents/{doc_id}").status_code)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        emit("NETWORK_FAIL", type(exc).__name__)
        raise SystemExit(1) from exc
