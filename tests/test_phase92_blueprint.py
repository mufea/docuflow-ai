from __future__ import annotations

from pathlib import Path


def _active_blueprint() -> str:
    lines = []
    for line in Path("infra/render.yaml").read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def test_blueprint_uses_inline_jobs_and_single_cleanup_cron() -> None:
    active = _active_blueprint()
    text = Path("infra/render.yaml").read_text()
    assert "JOB_BROKER" in active
    assert "value: inline" in active
    assert "type: cron" in active
    assert "python -m docuflow.cleanup" in active
    assert "CLEANUP_INTERVAL_SECONDS" in active
    assert 'value: "0"' in active
    assert "type: worker" not in active
    assert "docuflow-worker" not in active
    assert "JOB_BROKER=rq" not in active
    assert "docuflow-redis" in active
    assert "AI_PROVIDER" in active
    assert "value: mock" in active
    assert "infra/render.scaling.yaml" in text or Path("infra/render.scaling.yaml").is_file()


def test_scaling_blueprint_documents_rq_worker() -> None:
    scaling = Path("infra/render.scaling.yaml").read_text()
    assert "type: worker" in scaling
    assert "JOB_BROKER" in scaling
    assert "value: rq" in scaling
    assert "docuflow-worker" in scaling
