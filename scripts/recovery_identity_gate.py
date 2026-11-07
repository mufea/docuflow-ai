#!/usr/bin/env python3
"""Classify a recovery/inspect DSN without connecting or printing secrets.

Never prints DATABASE_URL, username, password, or query parameters.
Never opens a database connection. Never runs Alembic or SQL.

Exit 0 only when the mode is allowed for the classification.
Exit 1 on STOP. Exit 2 on invalid configuration.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import unquote, urlparse

PROD_SERVICE = "docuflow-db"
PROD_INSTANCE = "dpg-dbiqe70ae00c73cdif7g-a"
STAGING_SERVICE = "docuflow-staging-db"
STAGING_INSTANCE = "dpg-dbn71tec6qcc73cric9g-a"
STAGING_DATABASE = "docuflow_staging_db"
ALLOWED_MODES = {"inspect", "drill"}


def emit(label: str, value: object) -> None:
    print(f"{label} {value}", flush=True)


def _norm_host(value: str) -> str:
    return value.lower().strip().rstrip(".")


def _norm_name(value: str) -> str:
    return value.lower().strip()


def parse_dsn_identity(raw: str) -> tuple[str, str]:
    """Return (hostname, database) only. Discard user, password, query."""
    text = raw.strip()
    if not text:
        return "", ""
    parsed = urlparse(text)
    host = _norm_host(parsed.hostname or "")
    name = _norm_name(unquote((parsed.path or "/").lstrip("/").split("/")[0]))
    return host, name


def hosts_match(actual: str, expected: str) -> bool:
    a, e = _norm_host(actual), _norm_host(expected)
    if not a or not e:
        return False
    return a == e or a.startswith(e + ".") or e in a


def is_production_service(service: str) -> bool:
    return _norm_name(service) == PROD_SERVICE


def is_staging_service(service: str) -> bool:
    value = _norm_name(service)
    return value == STAGING_SERVICE or "staging" in value


def is_production_host(host: str) -> bool:
    return PROD_INSTANCE in _norm_host(host)


def is_staging_host_or_db(host: str, database: str) -> bool:
    h, n = _norm_host(host), _norm_name(database)
    return STAGING_INSTANCE in h or "staging" in h or n == STAGING_DATABASE or "staging" in n


def approved_looks_like_drill(service: str) -> bool:
    value = _norm_name(service)
    if not value or is_production_service(value) or is_staging_service(value):
        return False
    return "restore" in value or "drill" in value


def classify(
    *,
    mode: str,
    approved_service: str,
    expected_host: str,
    actual_host: str,
    actual_database: str,
) -> tuple[str, str]:
    """Return (classification, stop_reason). stop_reason empty means proceed."""
    mode_l = _norm_name(mode)
    if mode_l not in ALLOWED_MODES:
        return "ambiguous", "invalid RECOVERY_MODE"
    if is_production_service(approved_service) or is_production_host(expected_host) or is_production_host(actual_host):
        cls = "production"
        if mode_l == "inspect" and is_production_host(actual_host):
            return cls, ""
        return cls, "production identity is not a drill target"
    if is_staging_service(approved_service) or is_staging_host_or_db(expected_host, "") or is_staging_host_or_db(
        actual_host, actual_database
    ):
        return "staging", "staging identity is not a drill target"
    if mode_l == "inspect":
        return "ambiguous", "inspect DSN is not classified production"
    if not approved_looks_like_drill(approved_service):
        return "ambiguous", "approved target must contain restore or drill and must not be production/staging"
    if not expected_host.strip():
        return "ambiguous", "EXPECTED_RESTORE_HOSTNAME is required before connecting"
    if not actual_host:
        return "ambiguous", "DATABASE_URL hostname missing; cannot map service to host"
    if not hosts_match(actual_host, expected_host):
        return "ambiguous", "DSN hostname does not match owner-confirmed restore hostname"
    return "isolated-restore", ""


def main() -> int:
    mode = os.environ.get("RECOVERY_MODE", "").strip()
    approved = os.environ.get("OWNER_APPROVED_RECOVERY_TARGET", "").strip()
    expected = os.environ.get("EXPECTED_RESTORE_HOSTNAME", "").strip()
    raw = os.environ.get("DATABASE_URL", "")
    host, database = parse_dsn_identity(raw)
    emit("mode", mode or "missing")
    emit("approved_target_set", "yes" if approved else "no")
    emit("expected_host_set", "yes" if expected else "no")
    emit("dsn_present", "yes" if raw.strip() else "no")
    emit("host", host or "missing")
    emit("database", database or "missing")
    cls, reason = classify(
        mode=mode,
        approved_service=approved,
        expected_host=expected,
        actual_host=host,
        actual_database=database,
    )
    emit("classification", cls)
    if reason:
        emit("STOP", reason)
        return 2 if "invalid RECOVERY_MODE" in reason or reason.startswith("EXPECTED") else 1
    emit("proceed", cls)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — never dump DSN from unexpected errors
        emit("STOP", type(exc).__name__)
        raise SystemExit(1) from None
