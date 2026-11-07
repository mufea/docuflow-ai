from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "recovery_identity_gate",
    Path(__file__).resolve().parents[1] / "scripts" / "recovery_identity_gate.py",
)
assert _spec and _spec.loader
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
classify = _gate.classify
parse_dsn_identity = _gate.parse_dsn_identity

PROD = "dpg-dbiqe70ae00c73cdif7g-a"
STAGING = "dpg-dbn71tec6qcc73cric9g-a"
DRILL = "dpg-drillhostae00c73cdif7g-a"


def _run(extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("DATABASE_URL", "RECOVERY_MODE", "OWNER_APPROVED_RECOVERY_TARGET", "EXPECTED_RESTORE_HOSTNAME"):
        env.pop(key, None)
    env.update(extra)
    return subprocess.run(  # noqa: S603
        [sys.executable, "scripts/recovery_identity_gate.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_parse_dsn_discards_password() -> None:
    host, name = parse_dsn_identity("postgresql://u:super-secret@dpg-abc-a:5432/appdb?sslmode=require")
    assert host == "dpg-abc-a"
    assert name == "appdb"


def test_invalid_mode_stops() -> None:
    result = _run({"RECOVERY_MODE": "restore"})
    assert result.returncode != 0
    assert "invalid RECOVERY_MODE" in result.stdout


def test_drill_rejects_production_host_even_with_drill_name() -> None:
    cls, reason = classify(
        mode="drill",
        approved_service="docuflow-db-restore-drill-20261107",
        expected_host=DRILL,
        actual_host=PROD,
        actual_database="anything",
    )
    assert cls == "production"
    assert reason


def test_drill_rejects_staging() -> None:
    cls, reason = classify(
        mode="drill",
        approved_service="docuflow-db-restore-drill-20261107",
        expected_host=DRILL,
        actual_host=STAGING,
        actual_database="docuflow_staging_db",
    )
    assert cls == "staging"
    assert reason


def test_drill_requires_expected_hostname() -> None:
    cls, reason = classify(
        mode="drill",
        approved_service="docuflow-db-restore-drill-20261107",
        expected_host="",
        actual_host=DRILL,
        actual_database="restoredb",
    )
    assert cls == "ambiguous"
    assert "EXPECTED_RESTORE_HOSTNAME" in reason


def test_drill_hostname_mismatch_is_ambiguous() -> None:
    cls, reason = classify(
        mode="drill",
        approved_service="docuflow-db-restore-drill-20261107",
        expected_host="dpg-otherhost-a",
        actual_host=DRILL,
        actual_database="restoredb",
    )
    assert cls == "ambiguous"
    assert "does not match" in reason


def test_drill_pass_when_host_matches_owner_confirmed() -> None:
    cls, reason = classify(
        mode="drill",
        approved_service="docuflow-db-restore-drill-20261107",
        expected_host=DRILL,
        actual_host=DRILL,
        actual_database="restoredb",
    )
    assert cls == "isolated-restore"
    assert reason == ""


def test_subprocess_does_not_print_dsn_or_password() -> None:
    secret = "never-print-this-password"
    result = _run(
        {
            "RECOVERY_MODE": "drill",
            "OWNER_APPROVED_RECOVERY_TARGET": "docuflow-db-restore-drill-20261107",
            "EXPECTED_RESTORE_HOSTNAME": DRILL,
            "DATABASE_URL": f"postgresql://owner:{secret}@{DRILL}/restoredb",
        }
    )
    assert result.returncode == 0
    assert secret not in result.stdout
    assert "postgresql://" not in result.stdout
    assert "classification isolated-restore" in result.stdout


def test_inspect_allows_production_host() -> None:
    result = _run(
        {
            "RECOVERY_MODE": "inspect",
            "DATABASE_URL": f"postgresql://u:x@{PROD}/unknown",
        }
    )
    assert result.returncode == 0
    assert "classification production" in result.stdout
    assert "x@" not in result.stdout
