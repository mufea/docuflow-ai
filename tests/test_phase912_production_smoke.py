from __future__ import annotations

import os
import subprocess
import sys


def _run(extra: dict[str, str] | None = None, *, unset: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in unset:
        env.pop(key, None)
    for key in list(env):
        if key.startswith("STAGING_") or key.startswith("PRODUCTION_"):
            env.pop(key, None)
    if extra:
        env.update(extra)
    return subprocess.run(  # noqa: S603
        [sys.executable, "scripts/production_smoke.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_production_smoke_refuses_without_opt_in() -> None:
    result = _run()
    assert result.returncode == 2
    assert "PRODUCTION_SMOKE_MUTATIONS" in result.stdout


def test_production_smoke_refuses_staging_env_mixup() -> None:
    result = _run(
        {
            "PRODUCTION_SMOKE_MUTATIONS": "1",
            "PRODUCTION_HOST_CONFIRM": "docuflowai.site",
            "STAGING_API_URL": "https://docuflow-staging-api.onrender.com",
        }
    )
    assert result.returncode == 2
    assert "STAGING_API_URL" in result.stdout


def test_production_smoke_refuses_wrong_host_confirm() -> None:
    result = _run(
        {
            "PRODUCTION_SMOKE_MUTATIONS": "1",
            "PRODUCTION_HOST_CONFIRM": "docuflow-staging-api.onrender.com",
        }
    )
    assert result.returncode == 2
    assert "PRODUCTION_HOST_CONFIRM" in result.stdout
