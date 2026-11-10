# Phase 10.3B — P0 correctness remediation

Conditional job completion and refund-protected credit settlement.

Time: **10 Nov 2026, 22:33 Asia/Jakarta (WIB)**.

## 1. Executive summary

Phase 10.3B implements the two approved P0 correctness fixes from the
Phase 10.3A assessment (PR [#55](https://github.com/mufea/docuflow-ai/pull/55)):

1. **P0-A.** Complete a job only when the database row is still
   `processing`. The predicate is enforced by
   `UPDATE jobs … WHERE id = :id AND status = 'processing'`.
2. **P0-B.** Refuse credit settlement when `refund:{job_id}` already
   exists. The check runs after the existing `CreditAccount` `SELECT FOR
   UPDATE`, so a concurrent refund and settlement cannot both succeed.

No schema migration, Redis, worker, heartbeat, stale-recovery, or
result-persistence change is included. Staging and production were not
mutated.

## 2. Repository baseline

| Item | Value |
| --- | --- |
| Expected `origin/main` | `fdf5b65952b6a245dbdc9a30a190a39eafff24a5` |
| Actual `origin/main` | `fdf5b65952b6a245dbdc9a30a190a39eafff24a5` (match) |
| Feature branch | `feat/phase-10-3b-p0-correctness` |
| Implementation commit | recorded in `docs/IMPLEMENTATION_STATUS.md` after commit |
| Production / staging runtime | **NOT VERIFIED** |
| Deploy | **NOT EXECUTED** |

Working tree at branch creation was clean. No user changes were discarded.

## 3. Scope and exclusions

In scope:

- Atomic completion predicate (`status = 'processing'`).
- Settlement refusal when `refund:{job_id}` exists.
- Focused SQLite unit tests and PostgreSQL concurrency tests.
- Status-label correction for merged Phase 10.2 / 10.3A PRs.

Out of scope (unchanged):

- Heartbeat / leases / `JOB_STALE_MINUTES`.
- Stale-job requeue or resume of `processing`.
- Result persistence (`DocumentService._store` still commits before
  completion).
- Object storage, API auth, rate limiting, frontend, Render, Redis.

## 4. Original defects

| ID | Location | Previous behavior |
| --- | --- | --- |
| F09 | `JobRunner.process` assigned `job.status = "completed"` | A stale-cleanup `UPDATE … WHERE status='processing'` could lose, then the worker still committed `completed` and settled credits |
| F14 | `CreditService.settle` | Idempotent on `settle:{job_id}` only; did not inspect `refund:{job_id}` |

## 5. P0-A — Conditional job completion

| Field | Detail |
| --- | --- |
| Files | `src/docuflow/jobs/completion.py` (new), `src/docuflow/jobs/runner.py` |
| Functions | `complete_job_if_processing()`, `JobRunner.process()` |
| Previous | ORM mutation `job.status = "completed"` with no SQL predicate |
| New | `UPDATE jobs SET status='completed', progress=100, completed_at=…[, result_payload, result_document_ids] WHERE id=:id AND status='processing'` |
| Zero rows | `JobCompleteResult.claimed is False`; runner rolls back and returns without settling |
| Missing job | `claimed is False`, `previous_status is None` |
| Callers | `JobRunner.process` inspects `claimed`. Unsuccessful completion is not treated as success and does not call `settle` |

Acceptance:

- `processing` → complete allowed.
- `queued` / `failed` / `completed` / missing → no update.
- Concurrent completes: exactly one `claimed=True`.
- Concurrent complete vs `fail_job_and_refund`: one terminal status;
  not both `settle:` and `refund:` ledger rows.

## 6. P0-B — Refund-protected settlement

| Field | Detail |
| --- | --- |
| Files | `src/docuflow/billing/ledger.py` |
| Function | `CreditService.settle()` |
| Previous | After account lock, return if `settle:{job_id}` exists; otherwise write settle |
| New | After the same lock, return if `settle:{job_id}` exists; **raise** `ConflictError` if `refund:{job_id}` exists; otherwise write settle |
| Refusal | No `settle:` or `release-settle:` row; reserved/balance unchanged; refund row unchanged |
| Idempotency | Repeat settle after a successful settle still no-ops |
| Retry | Repeat settle after a refund still raises `ConflictError` (`retryable=False`) |
| DB errors | `OperationalError` / `IntegrityError` are not caught by `settle` |

`ConflictError` is a `DocuflowError`. If the runner has already
conditionally completed in the same uncommitted transaction and then
`settle` raises, the `except DocuflowError` path rolls back the complete
and calls `fail_job_and_refund` (refund is idempotent).

## 7. Transaction and concurrency guarantees

**Jobs.** PostgreSQL takes a row lock for `UPDATE jobs … WHERE id AND
status='processing'`. A second complete or a `fail_job_and_refund`
update waits, then sees either `rowcount=1` or `0`. Application-level
`if job.status == "processing"` is not used as the authority.

**Credits.** `settle` and `refund_reservation` both `SELECT … FOR UPDATE`
the `credit_accounts` row before reading ledger keys and writing.
Interleaving “check then write” across two transactions is prevented by
that lock. Distinct idempotency keys (`settle:{id}` vs `refund:{id}`)
cannot by themselves exclude both rows; the lock plus the new refund
check provides the invariant. No schema change.

SQLite `FOR UPDATE` is not a lock. SQLite tests prove sequential
behavior only.

## 8. Tests added

`tests/test_phase103b_p0_correctness.py` (SQLite):

- Processing complete; queued/failed/completed rejected; missing job;
  completed cannot complete again; fail-then-complete does not
  overwrite failure.
- Runner success path completes and settles.
- Runner mid-flight fail does not settle.
- Settle without refund; repeat settle; settle after refund raises
  `ConflictError` with no settle row; refund remains idempotent;
  `OperationalError` from `flush` is not treated as success.

`tests/integration/test_postgres_reliability.py` (PostgreSQL):

- Concurrent completes: one winner; loser does not overwrite payload.
- Concurrent complete+settle vs fail+refund: one terminal state; not
  both ledger keys.
- Concurrent settle vs refund: exactly one of `settle:` / `refund:`.
- Runner skips settle after lost completion.

## 9. Tests executed and results

All with `env -u DATABASE_URL`. Production DSN was not used.
`TEST_DATABASE_URL` host `127.0.0.1` database `docuflow_test` only.

| Command | Exit |
| --- | --- |
| `uv run pytest -q tests/test_phase103b_p0_correctness.py tests/test_credits.py tests/test_phase92_refunds.py` | **0** (28 passed) |
| `uv run pytest -q tests/integration/test_postgres_reliability.py tests/test_jobs_and_security.py` | **0** (18 passed) |
| `uv run pytest -q tests/test_phase91_cleanup.py tests/test_phase9_integrity.py -k 'job or credit or refund or settle or fail'` | **0** (9 passed, 7 deselected) |
| `uv run ruff check src tests scripts` | **0** |
| `uv run mypy src/docuflow` | **0** |
| `git diff --check` | **0** |

PostgreSQL concurrency tests: **PASS** (local isolated `docuflow_test`).
CI: **NOT VERIFIED** at documentation time.

## 10. Known limitations

- Interrupted `processing` jobs still wait for stale cleanup
  (`JOB_STALE_MINUTES` + cron). No resume.
- `_store` still commits documents before job completion (Phase 10.3C).
- Completing a job that lost the race leaves stored result objects
  orphaned; that is existing F06/F07 behavior.
- Heartbeat is unchanged.

## 11. Migration status

**None.** No Alembic revision. No ledger or jobs schema change.

## 12. Deployment considerations

Application-only change. Safe with the current inline broker and
PostgreSQL. No env vars, Render Blueprint, or start-command edits.
Not production-verified.

## 13. Rollback considerations

Revert the PR. Jobs again complete without a status predicate; `settle`
again ignores `refund:{job_id}`. No migration to reverse.

## 14. Remaining Phase 10.3C work

Stop committing `Document` rows before the job completion transaction.
Record job-scoped result identity (schema TBD). Detect and reconcile
orphans. Do not retry `processing` until result persistence is
idempotent.
