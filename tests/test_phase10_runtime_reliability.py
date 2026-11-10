from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docuflow.jobs.broker import InlineBroker
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload


def _track_named_tempfiles(monkeypatch) -> list[Path]:
    created: list[Path] = []
    original = tempfile.NamedTemporaryFile

    def tracking(*args, **kwargs):
        handle = original(*args, **kwargs)
        created.append(Path(handle.name))
        return handle

    monkeypatch.setattr("docuflow.api.routes.documents.tempfile.NamedTemporaryFile", tracking)
    return created


def test_oversized_upload_unlinks_tempfile(client: TestClient, app, monkeypatch) -> None:
    app.state.ctx.settings.max_upload_bytes = 64
    created = _track_named_tempfiles(monkeypatch)
    auth = register_and_login(client, "upload-size@example.com")
    payload = b"x" * 200
    response = client.post(
        "/v1/documents",
        files={"file": ("too-big.bin", payload, "application/octet-stream")},
        headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
    )
    assert response.status_code == 413, response.text
    assert created
    assert all(not path.exists() for path in created)


def test_rejected_upload_unlinks_tempfile(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    created = _track_named_tempfiles(monkeypatch)
    auth = register_and_login(client, "upload-reject@example.com")
    fake = tmp_path / "notes.pdf"
    fake.write_text("not a pdf")
    with fake.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": ("notes.pdf", handle, "application/pdf")},
            headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
        )
    assert response.status_code in {400, 415}
    assert created
    assert all(not path.exists() for path in created)


def test_failed_storage_download_unlinks_tempfile(
    client: TestClient, app, tmp_path: Path, monkeypatch
) -> None:
    created = _track_named_tempfiles(monkeypatch)
    auth = register_and_login(client, "download-fail@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "ok.pdf", ["ok"]), auth["csrf"])
    original = app.state.ctx.storage.download

    def boom(key: str, dest: Path) -> Path:
        dest.write_bytes(b"partial")
        raise RuntimeError("download failed")

    app.state.ctx.storage.download = boom  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="download failed"):
            client.get(f"/v1/documents/{doc_id}/download")
    finally:
        app.state.ctx.storage.download = original  # type: ignore[method-assign]
    assert created
    assert all(not path.exists() for path in created)


def test_inline_broker_shutdown_waits_for_inflight() -> None:
    started = threading.Event()
    finished = threading.Event()

    class SlowRunner:
        def process(self, job_id: str) -> None:
            started.set()
            time.sleep(0.15)
            finished.set()

    broker = InlineBroker(SlowRunner(), workers=1)  # type: ignore[arg-type]
    broker.enqueue("job-shutdown")
    assert started.wait(timeout=1)
    broker.shutdown(wait=True)
    assert finished.is_set()
    with pytest.raises(RuntimeError):
        broker.enqueue("job-after-shutdown")


def test_lifespan_shuts_down_inline_pool(app) -> None:
    with TestClient(app):
        pass
    with pytest.raises(RuntimeError):
        app.state.ctx.broker.enqueue("after-lifespan")
