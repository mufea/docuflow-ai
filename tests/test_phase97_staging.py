from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from docuflow.jobs.recovery import QUEUED_RECOVERY_LIMIT


def _active(path: str) -> str:
    lines = []
    for line in Path(path).read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def test_production_blueprint_service_names_unchanged() -> None:
    active = _active("infra/render.yaml")
    assert "name: docuflow-api" in active
    assert "name: docuflow-web" in active
    assert "name: docuflow-db" in active
    assert "name: docuflow-cleanup" in active
    assert "type: worker" not in active
    assert "healthCheckPath: /health" in Path("infra/render.yaml").read_text()
    assert "value: inline" in active


def test_staging_blueprint_is_isolated_and_inline() -> None:
    text = Path("infra/render.staging.yaml").read_text()
    active = _active("infra/render.staging.yaml")
    assert "name: docuflow-staging-api" in active
    assert "name: docuflow-staging-web" in active
    assert "name: docuflow-staging-db" in active
    assert "name: docuflow-staging-cleanup" in active
    assert "name: docuflow-api" not in active
    assert "name: docuflow-db" not in active
    assert "type: worker" not in active
    assert "docuflow-worker" not in active
    assert "JOB_BROKER" in active
    assert "value: inline" in active
    assert "healthCheckPath: /health" in text
    assert "value: mock" in active
    assert "value: console" in active
    assert "python -m docuflow.migrate" in active


def test_queued_recovery_limit_remains_one_hundred() -> None:
    assert QUEUED_RECOVERY_LIMIT == 100


def test_staging_smoke_is_not_executed_without_url(monkeypatch) -> None:
    monkeypatch.delenv("STAGING_API_URL", raising=False)
    env = os.environ.copy()
    env.pop("STAGING_API_URL", None)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/staging_smoke.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "NOT EXECUTED" in result.stdout
    assert "postgres://" not in result.stdout.lower()
