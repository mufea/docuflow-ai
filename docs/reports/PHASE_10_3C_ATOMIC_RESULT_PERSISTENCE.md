# Phase 10.3C — Atomic result persistence and deferred document commit

Time: **11 Nov 2026, 06:44 Asia/Jakarta (WIB)**.

## 1. Objective and baseline

Defer generated result `Document` row commits until the job runner’s
final PostgreSQL transaction, which also performs conditional completion
and refund-protected settlement.

| Item | Value |
| --- | --- |
| Original baseline | `37412e965f286ffa34122645d2a9ddd13c742e23` (PR #56 merge) |
| Branch | `feat/phase-10-3c-atomic-result-persistence` |
| Implementation commit | `5eb04d10653fde60256f748078dc00ccabde1921` |
| Target | `main` |
| Deploy | **NOT EXECUTED** |

Phase 10.3A documented the original `_store` commit-before-complete
defect (F06/F07). That historical finding is unchanged. This phase
implements Option C for the **database** side only.

## 2. Original persistence problem

`DocumentService._store()` committed each result row immediately.
`JobRunner._execute` then completed and settled in a later transaction.

If completion lost a race, settlement failed, or processing failed after
the first output, committed `Document` rows could remain while the job
became `failed` and credits were refunded.

## 3. Implementation approach

Smallest change:

- `store_upload()` still commits (ordinary uploads).
- `store_result(*, commit=True)` keeps the previous default.
- The job runner calls `store_result(..., commit=False)`.
- `_store` then `flush()` + `refresh()` so IDs exist without committing.
- The runner’s existing `complete_job_if_processing` + `settle` +
  `session.commit()` path is the single DB commit for success.

No schema, no `job_id` column, no Redis, no object-store reconciler.

## 4. Deferred document commit behavior

| Caller | Commit |
| --- | --- |
| `store_upload` | `commit=True` (unchanged) |
| `store_result` default | `commit=True` (backward compatible) |
| `JobRunner._execute` | `commit=False` → `flush()` only |

Flushed rows are visible in the same session (IDs available). They are
not visible to other sessions until the runner commits.

## 5. Final database transaction sequence

1. Claim `queued` → `processing` (existing commit).
2. Download inputs and run the operation.
3. Progress 25/80 commits remain (before result rows).
4. Upload generated files to object storage.
5. Insert result `Document` rows and `flush()`.
6. `complete_job_if_processing()` (`WHERE status='processing'`).
7. If `claimed` is false: `rollback()`, return, do not settle.
8. `CreditService.settle()` (refuses `refund:{job_id}`).
9. One `session.commit()` covering result rows, completed job,
   `result_document_ids` / payload, ledger, and balance.

Phase 10.3B guards are preserved.

## 6. Rollback scenarios and results

| Scenario | Database | Credits |
| --- | --- | --- |
| Processing failure | Result rows not persisted; `_fail` + refund | Refunded |
| Later output fails after earlier `flush` | All uncommitted result rows rolled back | Refunded |
| Completion loses race | Result rows rolled back; no settle | Existing refund |
| Settlement raises | Complete + result rows rolled back; then fail+refund | Refunded |
| Final commit fails | Same exception path: rollback then `_fail` | Refunded |

After `rollback()`, `_fail` / `fail_job_and_refund` uses the same
session successfully.

## 7. Regression tests and outcomes

All with `env -u DATABASE_URL`. Production DSN unused.

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/test_phase103c_result_persistence.py` | **8 passed** |
| Document-service (`test_phase92_storage`, `test_phase91_cleanup`, `test_phase93_reliability`, `test_phase94_storage`) | **47 passed** |
| Job runner/completion (`test_jobs_and_security`, `test_phase103b_p0_correctness`, `test_broker`, `test_phase10_runtime_reliability`) | **28 passed** |
| Billing (`test_credits`, `test_phase92_refunds`) | **14 passed** |
| CI-equivalent `pytest -q -m "not integration"` | **289 passed**, 1 skipped |
| CI-equivalent `pytest -q -m integration` | **20 passed** |
| `uv run pytest -q` (unit+integration together) | **308 passed**, 1 skipped, **1 failed** (see below) |
| `uv run ruff check src tests scripts` | **0** |
| `uv run mypy src/docuflow` | **0** |
| `git diff --check` | **0** |

The combined `pytest -q` failure was
`tests/test_phase94_storage.py::test_access_denied_logs_classification_without_secrets`
(empty `caplog`). That test **passed** in isolation and in the
document-service group. It is **not** in the 10.3C diff (S3 logging).
CI-equivalent unit tests (the command GitHub runs) passed. Treated as an
order-dependent logging capture flake, not a 10.3C defect.

`ruff format --check` reports pre-existing files outside this phase
plus wrapping in 10.3B lines of `test_postgres_reliability.py`. CI runs
`ruff check`, not format. Those files were not reformatted.

## 8. PostgreSQL integration-test status

**PASS** against local isolated `TEST_DATABASE_URL` host `127.0.0.1`
database `docuflow_test`. Not production.

Covered:

- Deferred result row invisible to another session until commit.
- Rollback drops the row; object may remain.
- Lost completion rolls back a flushed result and does not settle.

SQLite tests are sequential only. They are not proof of PostgreSQL
locking.

## 9. Object-storage atomicity limitation

PostgreSQL cannot include S3/R2/`FilesystemStorage.put` in the same
transaction. If upload succeeds and the DB rolls back, the object can
remain. Tests assert that leftover object after rollback. **No**
automatic delete and **no** orphan reconciler in this phase.

Do not claim cross-system atomicity between PostgreSQL and object
storage.

## 10. Schema / migration status

**None.** No Alembic revision. No `job_id` column.

## 11. Remaining risks and non-goals

Unchanged / out of scope:

- Heartbeat, stale-job resume, Redis/RQ, outbox.
- Orphan object reconciliation.
- Retry after `_store` (still unsafe for object duplicates).
- Render, env, frontend.

Interrupted `processing` still waits for stale cleanup.

## 12. CI and PR evidence

Recorded after PR creation. Documentation-time CI: **NOT VERIFIED**.

## 13. Staging and production verification

STAGING VERIFIED: **NOT VERIFIED**.
PRODUCTION VERIFIED: **NOT VERIFIED**.

No staging or production mutation, migration, deploy, or DSN use.
GitHub CI is not runtime verification.
