from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf


def _upload(client: TestClient, path: Path, csrf: str) -> str:
    with path.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": (path.name, handle, "application/pdf")},
            headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
        )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _wait_job(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/v1/jobs/{job_id}").json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_merge_job_and_download(client: TestClient, tmp_path: Path) -> None:
    session = register_and_login(client)
    csrf = session["csrf"]
    first = write_text_pdf(tmp_path / "a.pdf", ["Alpha one", "Alpha two"])
    second = write_text_pdf(tmp_path / "b.pdf", ["Beta one"])
    left = _upload(client, first, csrf)
    right = _upload(client, second, csrf)
    created = client.post(
        "/v1/jobs",
        json={"operation": "merge", "document_ids": [left, right], "params": {}, "idempotency_key": "merge-1"},
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert created.status_code == 200, created.text
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "completed", job
    assert job["result_document_ids"]
    again = client.post(
        "/v1/jobs",
        json={"operation": "merge", "document_ids": [left, right], "params": {}, "idempotency_key": "merge-1"},
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert again.json()["id"] == created.json()["id"]
    download = client.get(f"/v1/documents/{job['result_document_ids'][0]}/download")
    assert download.status_code == 200
    assert download.content[:5] == b"%PDF-"


def test_upload_rejects_spoofed_pdf(client: TestClient, tmp_path: Path) -> None:
    session = register_and_login(client)
    fake = tmp_path / "notes.pdf"
    fake.write_text("not a pdf")
    with fake.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": ("notes.pdf", handle, "application/pdf")},
            headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
        )
    assert response.status_code in {400, 415}


def test_cross_user_document_access_denied(client: TestClient, tmp_path: Path) -> None:
    first = register_and_login(client, "one@example.com")
    pdf = write_text_pdf(tmp_path / "doc.pdf", ["private text"])
    doc_id = _upload(client, pdf, first["csrf"])
    client.post("/v1/auth/logout")
    register_and_login(client, "two@example.com")
    denied = client.get(f"/v1/documents/{doc_id}")
    assert denied.status_code == 403
    job = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": client.cookies.get("df_csrf"), "Origin": "http://testserver"},
    )
    assert job.status_code == 403


def test_path_traversal_filename_is_sanitized(client: TestClient, tmp_path: Path) -> None:
    session = register_and_login(client)
    pdf = write_text_pdf(tmp_path / "ok.pdf", ["safe"])
    with pdf.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": ("../etc/passwd.pdf", handle, "application/pdf")},
            headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
        )
    assert response.status_code == 200
    assert "/" not in response.json()["original_filename"]
    assert ".." not in response.json()["original_filename"]
