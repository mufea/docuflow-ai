# Phase 10.0A — Runtime reliability audit, targeted fixes, and regression tests

Repository-level code, tests, and documentation only. **Not** a restore,
export, cutover, or production change.

Time: **10 Nov 2026, 19:42 Asia/Jakarta (WIB)** (`2026-11-10T12:42:03Z`).
Base `origin/main`: **`3f8e4f7bb0e044d70c63e02bfba4fea3828930e4`**
(PR #48 merge; confirmed after `git fetch origin`).

## 1. Executive summary

Static inspection of `origin/main` found two temp-file leaks and a missing
inline-broker shutdown on API lifespan exit. Small fixes and regression
tests were added. Job claim/recovery/credit behavior was already covered
and was **not** redesigned.

This is **not** production runtime verification. CI success is not
production reliability.

## 2. Repository baseline

| Item | Value | Classification |
| --- | --- | --- |
| Audit time (UTC) | 2026-11-10T12:42:03Z | **VERIFIED** |
| `origin/main` | `3f8e4f7bb0e044d70c63e02bfba4fea3828930e4` | **VERIFIED** |
| Working tree before edits | clean | **VERIFIED** |
| Open PRs at audit | none | **VERIFIED** |

The agent environment had `DATABASE_URL` pointing at the production
Render Postgres hostname. That variable was **unset for every test
command**. The value was **not** printed, copied, or used. Production
SQL: **NOT EXECUTED**.

## 3. Audited files

- `src/docuflow/api/routes/documents.py`
- `src/docuflow/services/documents.py` (store_upload size check; unchanged)
- `src/docuflow/jobs/broker.py`
- `src/docuflow/jobs/recovery.py`
- `src/docuflow/jobs/runner.py` (claim `UPDATE … WHERE status=queued`)
- `src/docuflow/jobs/retention.py` (stale processing cleanup)
- `src/docuflow/main.py` (lifespan)
- `tests/test_broker.py`, `tests/test_phase96_safety.py`, `tests/test_jobs_and_security.py`

## 4. Confirmed findings

| ID | Finding | Classification |
| --- | --- | --- |
| A1 | Upload `NamedTemporaryFile(delete=False)` leaked when size validation raised **before** `tmp_path` was assigned and the post-`with` `finally` ran | **CONFIRMED** (code) → **FIXED** → **TESTED** (local pytest) |
| B1 | Download created a temp file, then `storage.download` could raise and leave a partial file; cleanup was only a `FileResponse` background task | **CONFIRMED** (code) → **FIXED** → **TESTED** (local pytest) |
| C1 | FastAPI lifespan stopped the cleanup scheduler but never shut down `InlineBroker`’s `ThreadPoolExecutor` | **CONFIRMED** (code) → **FIXED** → **TESTED** (local pytest) |

Job recovery, duplicate claim, and credit settlement were already
implemented (`recover_queued_jobs`, runner claim, `cleanup_abandoned_jobs`,
9.6 tests). No additional defect was demonstrated there.

| Area | Result |
| --- | --- |
| Queued job recovery on restart | Existing tests **TESTED** locally; no new defect |
| Stale `processing` jobs | Existing cleanup path; **TESTED** in 9.6 tests |
| Duplicate execution / concurrent claim | Runner `rowcount != 1` skip; **TESTED** |
| Credit reserve/settle | Existing 9.6 tests; **NOT** changed |
| In-flight interruption / SIGKILL | Inherent inline-broker limitation; **NOT** redesigned |

## 5. Already fixed before this phase

No prior commit on `origin/main` had the upload/download `finally` covering
the size-limit path or lifespan broker shutdown. Those were **not**
already fixed.

## 6. Changes implemented

1. Upload: bind `tmp_path` immediately; close the handle; `unlink` in an
   outer `finally` (size errors, store_upload errors, unexpected errors).
2. Download: `unlink` the dest file if `download` or `FileResponse`
   construction raises; successful responses still use `BackgroundTask`.
3. `InlineBroker.shutdown` / `RQBroker.shutdown`; lifespan calls
   `shutdown(wait=True)` after `scheduler.stop()`.
4. Regression tests in `tests/test_phase10_runtime_reliability.py`.
5. This report and a Phase 10.0A status entry. Phase 9.29 current status
   set to **MERGED** (PR #48, `3f8e4f7`) because this file was already
   being updated.

API contracts, storage providers, credits, Blueprint, and job status
values are unchanged.

## 7. Regression tests added

- `test_oversized_upload_unlinks_tempfile`
- `test_rejected_upload_unlinks_tempfile`
- `test_failed_storage_download_unlinks_tempfile`
- `test_inline_broker_shutdown_waits_for_inflight`
- `test_lifespan_shuts_down_inline_pool`

## 8. Commands executed and results

All pytest/ruff/mypy runs used `env -u DATABASE_URL`.

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/test_phase10_runtime_reliability.py tests/test_broker.py tests/test_jobs_and_security.py tests/test_phase96_safety.py` | **27 passed** |
| `uv run pytest -q -m "not integration"` | **251 passed**, 1 skipped, 13 deselected |
| `uv run pytest -q -m integration` | **13 passed**, 252 deselected (local `TEST_DATABASE_URL` on 127.0.0.1) |
| `uv run ruff check src tests scripts` | All checks passed |
| `uv run mypy src/docuflow` | Success, 73 source files |
| `git diff --check` | pass |
| Web lint/typecheck/tests/build | **NOT EXECUTED** (no web/shared-interface change) |

Local pytest is **not** production runtime verification.

## 9. Remaining runtime limitations

Inline broker (`JOB_BROKER=inline`, production’s current mode):

- Jobs run in-process threads. SIGKILL / crash still leaves `processing`
  rows until stale cleanup.
- `shutdown(wait=True)` can delay API exit until in-flight jobs finish a
  claim; it does **not** re-queue interrupted work.
- `_inflight` dedupe is **process-local**. Recovered `queued` rows are
  safe because the runner claims with `status=queued`.
- No Redis/worker was added. RQ remains unused unless configured.

Upload/download:

- Successful filesystem downloads still rely on Starlette
  `BackgroundTask` to unlink after the response. That path was unchanged.
- Signed-URL (S3) downloads never create a local temp file.

## 10. Production and infrastructure verification

| Item | Status |
| --- | --- |
| Production DSN used | **NOT EXECUTED** |
| Production SQL / restore / export | **NOT EXECUTED** |
| Render / Blueprint / paid services | **NOT EXECUTED** |
| Production runtime reliability | **NOT VERIFIED** |
| Staging runtime reliability | **NOT VERIFIED** |

## 11. Final classification

PHASE 10.0A IMPLEMENTATION: **COMPLETE – UNMERGED** (this PR; not
**MERGED** until it lands).
LOCAL VALIDATION: **TESTED** (pytest / ruff / mypy as above).
PRODUCTION VERIFIED: **NOT VERIFIED**.
PHASE_9_15: **OPEN**.
BACKUP_ASSURANCE: **INCOMPLETE**.
BUSINESS_RTO_CAPABILITY: **NOT DEMONSTRATED**.
BUSINESS_RPO_CAPABILITY: **NOT DEMONSTRATED**.
PRODUCTION_DR_READINESS: **NOT DEMONSTRATED**.
