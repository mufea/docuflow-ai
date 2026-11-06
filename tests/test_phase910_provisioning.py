from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from pydantic import SecretStr

from docuflow.config import Settings
from docuflow.staging_checks import audit_staging_blueprint, validate_staging_configuration


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
        "cleanup_interval_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


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


def test_staging_blueprint_yaml_and_provisioning_invariants() -> None:
    text = Path("infra/render.staging.yaml").read_text()
    issues = audit_staging_blueprint(text)
    assert issues.errors == []
    assert "postgresMajorVersion: 16" in text
    assert "generateValue: true" in text
    assert "CLEANUP_INTERVAL_SECONDS" in text
    active = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "type: redis" not in active
    assert "type: worker" not in active


def test_audit_rejects_paid_postgres_and_nonzero_cleanup() -> None:
    text = Path("infra/render.staging.yaml").read_text()
    paid = text.replace("plan: free\n    postgresMajorVersion: 16", "plan: basic-256mb\n    postgresMajorVersion: 16")
    issues = audit_staging_blueprint(paid)
    assert any("PostgreSQL plan" in item for item in issues.errors)
    interval = text.replace(
        '      - key: CLEANUP_INTERVAL_SECONDS\n        value: "0"',
        '      - key: CLEANUP_INTERVAL_SECONDS\n        value: "900"',
    )
    issues = audit_staging_blueprint(interval)
    assert any("CLEANUP_INTERVAL_SECONDS=0" in item for item in issues.errors)


def test_audit_rejects_invalid_yaml() -> None:
    issues = audit_staging_blueprint("services: [\n  - name: broken")
    assert any("YAML is invalid" in item for item in issues.errors)


def test_config_rejects_live_keys_secret_reuse_and_cleanup_loop() -> None:
    ok = validate_staging_configuration(_staging_settings())
    assert ok.errors == []
    reused_secret = validate_staging_configuration(
        _staging_settings(),
        production_secret="unique-staging-secret-key-32chars!!",
    )
    assert any("unique secret" in item for item in reused_secret.errors)
    reused_key = validate_staging_configuration(
        _staging_settings(),
        production_s3_access_key_id="staging-key",
    )
    assert any("dedicated credentials" in item for item in reused_key.errors)
    live_ai = validate_staging_configuration(_staging_settings(ai_api_key=SecretStr("sk-live")))
    assert any("AI_API_KEY" in item for item in live_ai.errors)
    stripe = validate_staging_configuration(_staging_settings(stripe_secret_key=SecretStr("sk_live_x")))
    assert any("Stripe" in item for item in stripe.errors)
    loop = validate_staging_configuration(_staging_settings(cleanup_interval_seconds=900))
    assert any("CLEANUP_INTERVAL_SECONDS" in item for item in loop.errors)
    assert "sk-live" not in " ".join(live_ai.errors)
    assert "sk_live_x" not in " ".join(stripe.errors)


def test_preflight_rejects_production_secret_reuse_without_printing_it() -> None:
    result = _run(
        "scripts/staging_preflight.py",
        {
            "STAGING_PREFLIGHT": "1",
            "DOCUFLOW_ENV": "production",
            "DOCUFLOW_SECRET_KEY": "unique-staging-secret-key-32chars!!",
            "PRODUCTION_SECRET_KEY": "unique-staging-secret-key-32chars!!",
            "DATABASE_URL": "postgresql://u:p@docuflow-staging-db/docuflow_staging",
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": "docuflow-staging",
            "S3_ACCESS_KEY_ID": "staging-key",
            "S3_SECRET_ACCESS_KEY": "staging-secret",
            "JOB_BROKER": "inline",
            "AI_PROVIDER": "mock",
            "EMAIL_BACKEND": "console",
            "CLEANUP_INTERVAL_SECONDS": "0",
            "DOCUFLOW_PUBLIC_API_URL": "https://docuflow-staging-api.onrender.com",
            "DOCUFLOW_PUBLIC_WEB_URL": "https://docuflow-staging-web.onrender.com",
            "DOCUFLOW_CORS_ORIGINS": "https://docuflow-staging-web.onrender.com",
        },
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "unique secret" in result.stdout
    assert "unique-staging-secret-key-32chars!!" not in result.stdout
    assert "staging-secret" not in result.stdout
    assert "postgres://" not in result.stdout.lower()
