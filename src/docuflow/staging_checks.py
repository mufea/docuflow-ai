"""Staging safety helpers. Never print secrets, passwords, DSNs, or signed URLs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

import yaml  # type: ignore[import-untyped]

from docuflow.config import Settings
from docuflow.dsn import normalize_database_url

CheckStatus = Literal["PASS", "FAIL", "SKIPPED", "NOT EXECUTED"]

EXPECTED_ALEMBIC_HEAD = "0003_cost_efficient_reliability"
EXPECTED_PREVIOUS_REVISION = "0002_runtime_reliability"
QUEUED_RECOVERY_LIMIT_REQUIRED = 100

STAGING_SERVICE_NAMES = {
    "docuflow-staging-api",
    "docuflow-staging-web",
    "docuflow-staging-db",
    "docuflow-staging-cleanup",
}
PRODUCTION_SERVICE_NAMES = {
    "docuflow-api",
    "docuflow-web",
    "docuflow-db",
    "docuflow-cleanup",
    "docuflow-redis",
    "docuflow-worker",
}
STAGING_FORBIDDEN_SERVICE_NAMES = PRODUCTION_SERVICE_NAMES | {"docuflow-staging-redis"}
DEFAULT_PRODUCTION_BUCKETS = {"docuflow-documents"}
PRODUCTION_PUBLIC_HOSTS = {"docuflow-api", "docuflow-web"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

FORBIDDEN_FRAGMENTS = (
    "postgres://",
    "postgresql://",
    "postgresql+psycopg://",
    "redis://",
    "rediss://",
    "x-amz-signature",
    "x-amz-credential",
    "aws_secret",
    "password=",
    "secret_access_key",
    "akia",
)


@dataclass
class StagingIssues:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def sanitize_text(value: str) -> str:
    """Replace secret-like fragments so logs stay safe to print."""
    lowered = value.lower()
    redacted = value
    for fragment in FORBIDDEN_FRAGMENTS:
        idx = lowered.find(fragment)
        while idx != -1:
            end = idx
            while end < len(redacted) and not redacted[end].isspace():
                end += 1
            redacted = redacted[:idx] + "[redacted]" + redacted[end:]
            lowered = redacted.lower()
            idx = lowered.find(fragment)
    return redacted


def contains_secret_fragment(value: str) -> bool:
    lowered = value.lower()
    return any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS)


def emit(status: CheckStatus, name: str, detail: str = "") -> None:
    text = sanitize_text(detail).strip()
    if text:
        print(f"{status}: {name} — {text}")
    else:
        print(f"{status}: {name}")


def http_url_is_valid(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def database_identity(url: str) -> tuple[str, str]:
    """Return (hostname, database name). Never includes user or password."""
    normalized = normalize_database_url(url.strip())
    display = normalized
    if display.startswith("postgresql+psycopg://"):
        display = "postgresql://" + display.removeprefix("postgresql+psycopg://")
    parsed = urlparse(display)
    host = (parsed.hostname or "").lower()
    name = (parsed.path or "/").lstrip("/").split("?")[0]
    return host, name


def identity_label(host: str, name: str) -> str:
    return f"host={host or '<none>'} database={name or '<none>'}"


def _has_isolation_token(value: str) -> bool:
    lowered = value.lower()
    return "staging" in lowered or "test" in lowered


def is_production_database(
    host: str,
    name: str,
    *,
    production_host: str = "",
    production_name: str = "",
) -> bool:
    host_l = host.lower().strip()
    name_l = name.lower().strip()
    prod_host = production_host.lower().strip()
    prod_name = production_name.lower().strip()
    if prod_host and host_l and host_l == prod_host:
        return True
    if prod_name and name_l and name_l == prod_name:
        return True
    if _has_isolation_token(host_l) or _has_isolation_token(name_l):
        return False
    if host_l == "docuflow-db" or host_l.startswith("docuflow-db."):
        return True
    return name_l in {"docuflow", "docuflow_prod", "docuflow-db"}


def is_production_bucket(bucket: str, *, production_bucket: str = "") -> bool:
    name = bucket.strip().lower()
    if not name:
        return False
    prod = production_bucket.strip().lower()
    if prod and name == prod:
        return True
    if name in DEFAULT_PRODUCTION_BUCKETS:
        return True
    return False


def is_forbidden_live_test_bucket(bucket: str, *, production_bucket: str = "") -> bool:
    name = bucket.strip().lower()
    if not name:
        return True
    if is_production_bucket(name, production_bucket=production_bucket):
        return True
    if not _has_isolation_token(name) and name in DEFAULT_PRODUCTION_BUCKETS:
        return True
    return False


def hostname_from_url(url: str) -> str:
    return (urlparse(url.strip()).hostname or "").lower()


def is_loopback_host(host: str) -> bool:
    value = host.lower().strip().rstrip(".")
    return value in LOOPBACK_HOSTS


def opt_in_flag(name: str, raw: str | None) -> tuple[bool, str | None]:
    """Parse an explicit opt-in flag. Empty/unset/0 is off; 1 is on; anything else is invalid."""
    if raw is None:
        return False, None
    value = raw.strip()
    if value == "":
        return False, None
    if value == "0":
        return False, None
    if value == "1":
        return True, None
    return False, f"{name} must be unset, 0, or 1."


def smoke_target_errors(api_url: str, confirm: str = "") -> list[str]:
    """Refuse production and unconfirmed non-loopback smoke targets."""
    url = api_url.strip().rstrip("/")
    if not http_url_is_valid(url):
        return ["STAGING_API_URL must be an http:// or https:// URL."]
    parsed = urlparse(url)
    if parsed.path not in {"", "/"}:
        return ["STAGING_API_URL must be the API origin without an extra path."]
    host = hostname_from_url(url)
    if not host:
        return ["STAGING_API_URL has no hostname."]
    if is_production_public_host(host):
        return ["STAGING_API_URL points at a production API host."]
    if is_loopback_host(host):
        return []
    expected = confirm.strip().lower()
    if not expected:
        return ["STAGING_HOST_CONFIRM is required for non-loopback targets (API hostname)."]
    if expected != host:
        return ["STAGING_HOST_CONFIRM does not match the API hostname."]
    return []


def is_production_public_host(host: str) -> bool:
    value = host.lower().strip()
    if not value:
        return False
    if _has_isolation_token(value):
        return False
    if value in PRODUCTION_PUBLIC_HOSTS:
        return True
    return value.startswith("docuflow-api.") or value.startswith("docuflow-web.")


def confirm_matches(host: str, name: str, confirm: str) -> bool:
    expected = confirm.strip().lower()
    if not expected:
        return False
    if expected == name.lower():
        return True
    return expected == f"{host}/{name}".lower()


def active_yaml(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def blueprint_declared_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in active_yaml(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            names.add(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("name:"):
            names.add(stripped.split(":", 1)[1].strip())
    return names


def _service_env_item(service: dict[str, Any], key: str) -> dict[str, Any] | None:
    for item in service.get("envVars") or []:
        if isinstance(item, dict) and item.get("key") == key:
            return item
    return None


def _service_env_value(service: dict[str, Any], key: str) -> Any:
    item = _service_env_item(service, key)
    if item is None:
        return None
    return item.get("value")


def audit_staging_blueprint(text: str) -> StagingIssues:
    issues = StagingIssues()
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        issues.errors.append("Staging Blueprint YAML is invalid.")
        return issues
    if not isinstance(parsed, dict):
        issues.errors.append("Staging Blueprint YAML did not parse to a mapping.")
        return issues

    databases = [item for item in (parsed.get("databases") or []) if isinstance(item, dict)]
    staging_db = next((item for item in databases if item.get("name") == "docuflow-staging-db"), None)
    if staging_db is None:
        issues.errors.append("Staging Blueprint is missing database docuflow-staging-db.")
    else:
        version = staging_db.get("postgresMajorVersion")
        if version not in {16, "16"}:
            issues.errors.append("Staging PostgreSQL must declare postgresMajorVersion 16.")
        if str(staging_db.get("plan", "")).lower() != "free":
            issues.errors.append("Staging PostgreSQL plan must remain free in the default Blueprint.")

    services = [item for item in (parsed.get("services") or []) if isinstance(item, dict)]
    by_name = {str(item.get("name")): item for item in services}
    api = by_name.get("docuflow-staging-api") or {}
    web = by_name.get("docuflow-staging-web") or {}
    cleanup = by_name.get("docuflow-staging-cleanup") or {}
    if api:
        if str(api.get("plan", "")).lower() != "free":
            issues.errors.append("Staging API plan must remain free.")
        if _service_env_value(api, "JOB_BROKER") != "inline":
            issues.errors.append("Staging API JOB_BROKER must be inline.")
        if str(_service_env_value(api, "CLEANUP_INTERVAL_SECONDS")) != "0":
            issues.errors.append("Staging API must set CLEANUP_INTERVAL_SECONDS=0.")
        secret = _service_env_item(api, "DOCUFLOW_SECRET_KEY") or {}
        if secret.get("generateValue") is not True:
            issues.errors.append("Staging DOCUFLOW_SECRET_KEY must use generateValue so it is unique.")
        database = (_service_env_item(api, "DATABASE_URL") or {}).get("fromDatabase") or {}
        if database.get("name") != "docuflow-staging-db":
            issues.errors.append("DATABASE_URL must reference docuflow-staging-db only.")
        for key in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_ENDPOINT_URL"):
            item = _service_env_item(api, key) or {}
            if item.get("sync") is not False:
                issues.errors.append(f"{key} must remain owner-supplied (sync: false).")
    if web and str(web.get("plan", "")).lower() != "free":
        issues.errors.append("Staging web plan must remain free.")
    if cleanup:
        if cleanup.get("schedule") != "*/15 * * * *":
            issues.errors.append("Staging cleanup cron must stay on */15 * * * *.")
        for key in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_ENDPOINT_URL"):
            source = ((_service_env_item(cleanup, key) or {}).get("fromService") or {})
            if source.get("name") != "docuflow-staging-api":
                issues.errors.append(f"Cleanup {key} must copy from docuflow-staging-api, not production.")
        cleanup_db = (_service_env_item(cleanup, "DATABASE_URL") or {}).get("fromDatabase") or {}
        if cleanup_db.get("name") != "docuflow-staging-db":
            issues.errors.append("Cleanup DATABASE_URL must reference docuflow-staging-db only.")

    active = active_yaml(text)
    names = blueprint_declared_names(text)
    missing = sorted(STAGING_SERVICE_NAMES - names)
    if missing:
        issues.errors.append("Staging Blueprint is missing isolated services: " + ", ".join(missing))
    forbidden = sorted(names & STAGING_FORBIDDEN_SERVICE_NAMES)
    if forbidden:
        issues.errors.append("Staging Blueprint references production or Redis names: " + ", ".join(forbidden))
    if "type: redis" in active:
        issues.errors.append("Staging Blueprint still declares a Redis service.")
    if "type: worker" in active:
        issues.errors.append("Staging Blueprint must not declare a paid worker.")
    if "value: inline" not in active:
        issues.errors.append("Staging Blueprint must keep JOB_BROKER=inline.")
    if "value: mock" not in active:
        issues.errors.append("Staging Blueprint must keep AI_PROVIDER=mock.")
    if "value: console" not in active:
        issues.errors.append("Staging Blueprint must keep EMAIL_BACKEND=console.")
    if "healthCheckPath: /health" not in text:
        issues.errors.append("Staging API health check path must be /health.")
    if "python -m docuflow.migrate" not in active:
        issues.errors.append("Staging startup must run python -m docuflow.migrate.")
    if "fromDatabase:" in active and "docuflow-staging-db" not in active:
        issues.errors.append("Staging services must reference docuflow-staging-db.")
    if "docuflow-staging-redis" in active:
        issues.errors.append("Staging Blueprint must not reference docuflow-staging-redis.")
    if "REDIS_URL" in active:
        issues.errors.append("Staging Blueprint must not inject REDIS_URL while JOB_BROKER=inline.")
    return issues


def validate_staging_configuration(
    settings: Settings,
    *,
    production_s3_bucket: str = "",
    production_database_host: str = "",
    production_database_name: str = "",
    production_secret: str = "",
    production_s3_access_key_id: str = "",
) -> StagingIssues:
    issues = StagingIssues()
    if settings.env != "production":
        issues.errors.append("DOCUFLOW_ENV must be production so fail-fast validation applies.")
    issues.errors.extend(settings.production_readiness_errors())
    if settings.job_broker != "inline":
        issues.errors.append("JOB_BROKER must be inline. Staging must not use a paid worker or mandatory Redis.")
    if settings.ai_provider != "mock":
        issues.errors.append("AI_PROVIDER must remain mock in cost-efficient staging.")
    if settings.email_backend != "console":
        issues.errors.append("EMAIL_BACKEND must remain console in cost-efficient staging.")
    if not settings.cookie_secure:
        issues.errors.append("COOKIE_SECURE must be true for staging.")
    if settings.cleanup_interval_seconds != 0:
        issues.errors.append("CLEANUP_INTERVAL_SECONDS must be 0 so the staging cron is the only cleaner.")
    staging_secret = settings.secret_key.get_secret_value()
    if production_secret and staging_secret == production_secret:
        issues.errors.append("DOCUFLOW_SECRET_KEY matches the production secret. Staging requires a unique secret.")
    staging_access = settings.reveal_secret(settings.s3_access_key_id) or ""
    if production_s3_access_key_id and staging_access and staging_access == production_s3_access_key_id:
        issues.errors.append(
            "S3_ACCESS_KEY_ID matches a production access key. Staging requires dedicated credentials."
        )
    if settings.reveal_secret(settings.ai_api_key):
        issues.errors.append("AI_API_KEY must be unset in staging while AI_PROVIDER=mock.")
    if settings.reveal_secret(settings.stripe_secret_key) or settings.reveal_secret(settings.stripe_webhook_secret):
        issues.errors.append("Stripe credentials must be unset in staging.")
    if settings.reveal_secret(settings.midtrans_server_key):
        issues.errors.append("Midtrans credentials must be unset in staging.")
    host, name = database_identity(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        issues.errors.append("Staging DATABASE_URL must be PostgreSQL.")
    elif is_production_database(
        host,
        name,
        production_host=production_database_host,
        production_name=production_database_name,
    ):
        issues.errors.append("DATABASE_URL identity matches a production database. Use a dedicated staging database.")
    if is_production_bucket(settings.s3_bucket, production_bucket=production_s3_bucket):
        issues.errors.append("S3_BUCKET matches a production bucket. Staging requires a dedicated bucket.")
    api_host = hostname_from_url(settings.public_api_url)
    web_host = hostname_from_url(settings.public_web_url)
    if is_production_public_host(api_host):
        issues.errors.append("DOCUFLOW_PUBLIC_API_URL points at a production API host.")
    if is_production_public_host(web_host):
        issues.errors.append("DOCUFLOW_PUBLIC_WEB_URL points at a production web host.")
    if settings.job_broker == "inline":
        redis_host = hostname_from_url(settings.redis_url) if settings.redis_url.strip() else ""
        if (
            redis_host
            and not _has_isolation_token(redis_host)
            and (redis_host.startswith("docuflow-redis") or "docuflow-redis" in redis_host)
        ):
            issues.warnings.append(
                "REDIS_URL looks like production Redis. It is unused while JOB_BROKER=inline; leave it unset."
            )
    trusted = ",".join(settings.trusted_host_list)
    if api_host and api_host not in trusted and ".onrender.com" not in trusted:
        issues.warnings.append("DOCUFLOW_TRUSTED_HOSTS may not include the staging API host.")
    if not settings.cors_origin_list:
        issues.errors.append("DOCUFLOW_CORS_ORIGINS must include the staging web origin.")
    return issues


def expected_schema_gaps(table_columns: dict[str, set[str]], table_indexes: dict[str, set[str]]) -> list[str]:
    gaps: list[str] = []
    required_tables = {
        "cleanup_leases": {"name", "token", "locked_until", "acquired_at", "updated_at"},
        "storage_deletions": {"id", "storage_key", "status", "attempts", "started_at", "lease_until", "owner_token"},
        "jobs": {"id", "status", "operation"},
        "documents": {"id", "storage_key"},
        "users": {"id", "email"},
    }
    for table, columns in required_tables.items():
        present = table_columns.get(table, set())
        if not present:
            gaps.append(f"missing table {table}")
            continue
        missing = sorted(columns - present)
        if missing:
            gaps.append(f"missing {table} columns: {', '.join(missing)}")
    indexes = table_indexes.get("storage_deletions", set())
    if "ix_storage_deletions_lease_until" not in indexes:
        gaps.append("missing index ix_storage_deletions_lease_until")
    return gaps


def exit_code(statuses: list[CheckStatus]) -> int:
    if any(status == "FAIL" for status in statuses):
        return 1
    if statuses and all(status == "NOT EXECUTED" for status in statuses):
        return 2
    if not statuses:
        return 2
    return 0
