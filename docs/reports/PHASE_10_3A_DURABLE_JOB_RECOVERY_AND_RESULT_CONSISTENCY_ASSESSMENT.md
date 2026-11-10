# Phase 10.3A — Durable job recovery and result consistency assessment

Assessment-only. No application, schema, or infrastructure changes.
**Not** staging or production verification.

Time: **10 Nov 2026, 22:17 Asia/Jakarta (WIB)**.

Part 1 working paper:
`docs/reports/PHASE_10_3A_PART_1_REPOSITORY_AUDIT.md`.

## 1. Executive summary

The inline Postgres job path already prevents duplicate *execution* of
the same `queued` row and keeps **create+reserve** and **complete+settle**
in single database commits. It does **not** resume a `processing` job
after crash: recovery is delayed **fail+refund** after
`JOB_STALE_MINUTES` (source default 90).

Confirmed gaps that 10.3B should close **without Redis or a worker**:

| Gap | Class | Why it matters |
| --- | --- | --- |
| Completion is an unconditional ORM write | F09 | Can overwrite a concurrent stale `failed` |
| `settle` ignores `refund:{job_id}` | F14 | Can charge after a refund |
| `_store` `put`+commit before job complete | F06/F07 | Orphan objects and user-visible result docs on a failed job |
| No heartbeat during `_run_operation` | F04 | Live work can look abandoned if it exceeds the stale window |

Recommended architecture: **Option A (terminal-state + credit guards) first,
then Option C (bind result persistence to job completion)**. Option B
resume/retry is **not** first. Option D outbox is **not** required until
A+C still leave an S3/Postgres split that product cannot accept.

**P0 (one coordinated 10.3B unit):** conditional complete + settle-after-refund
refusal. **P1:** heartbeat during long ops; defer document commit; tests.
**P2:** orphan reconciler, observability, queued-recovery cap. **P3:**
resume/retry, outbox, RQ.

Phase 9.15 backup/DR status is **unchanged**.

## 2. Repository baseline

| Item | Value |
| --- | --- |
| `origin/main` | `2447ac516d29cfeb7d3297cfcefd6a9591343694` |
| Part 1 commit | `e46ed3747661b4387e95ade93289919d8b4f7bd6` |
| Branch | `audit/phase-10-3a-durable-job-recovery` |
| Part 1 recheck | Cited functions and line ranges still match (10 Nov 2026, 22:17 Asia/Jakarta) |
| Application diff vs `origin/main` | **None** (docs only on this branch) |

## 3. Scope and safety boundaries

In scope: job lifecycle, crash recovery, result persistence, credits,
roadmap, tests-as-plan.

Out of scope: implementation, migrations, Redis/RQ, Render changes,
staging/production mutation, backup/PITR, rate-limit work from 10.2.

## 4. Part 1 audit summary

Part 1 is **accepted**. Recheck did not upgrade or downgrade any F01–F15
class. Line references in Part 1 §11 still point at the same behavior.

Lifecycle remains `queued → processing → completed|failed` with
`cancelled` from `queued` only. No `processing → queued`.

## 5. Confirmed findings and evidence

Revalidated against current files:

| Finding | Evidence | Tests today |
| --- | --- | --- |
| Duplicate `queued` delivery is safe | `JobRunner.process` 52–66 `UPDATE … WHERE status=queued` | `test_duplicate_process_does_not_double_charge`, `test_duplicate_recovery_does_not_double_charge` |
| Processing is not resumed on start | `recover_queued_jobs` 25–29, 36–38 | `test_recovery_skips_processing_jobs_and_cleanup_fails_stale` |
| Stale path fails+refunds | `_fail_stale_jobs` 139–175; `fail_job_and_refund` | `test_stale_job_cleanup_is_idempotent` |
| Complete+settle one commit | `runner.py` 76–82 | `test_completed_job_records_settled_credits` |
| Refund after settle blocked | `ledger.py` 125–126 | `test_refund_does_not_run_after_settle` |
| Settle after refund **not** blocked | `settle` 86–87 checks only `settle:{job_id}` | **No test** |
| Complete has no status predicate | `job.status = "completed"` 77 | **No race test** |
| `_store` commits early | `put` 330 then `commit` 350; origin `job:{operation}` not job id (`runner.py` 144) | **No crash-after-store test** |
| Heartbeat only at claim / 25% / 80% | `_execute` 130–136 vs `_run_operation` 152–266 | — |
| SIGKILL skips `shutdown(wait=True)` | `main.py` 57–62 vs SIGKILL | Documented; not process-killed in CI |

These are **source + local-test** facts. They are **not** production
runtime guarantees.

## 6. Potential risks and unverified assumptions

Unchanged from Part 1 §10:

- Cleanup cron actually running: **NOT VERIFIED**.
- Live dashboard still `JOB_STALE_MINUTES=90`, `CLEANUP_INTERVAL_SECONDS=0`:
  **NOT VERIFIED**.
- F09 occurring in production: **NOT VERIFIED** (90-minute window).
- F12 under a real DB outage: **NOT VERIFIED**.

## 7. Failure scenario matrix

Part 1 §8 is the matrix of record. Classes unchanged:

- **VERIFIED SAFE:** F01, F08, F10, F14 (refund dup + refund-after-settle only)
- **VERIFIED UNSAFE:** F02–F07, F09 (race), F14 (settle-after-refund), F15
- **POTENTIAL RISK:** F09 overlap frequency, F12
- **NOT APPLICABLE / UNSAFE on user retry:** F11
- **CONFIRMED handled as error:** F13 (with partial F07 if some outputs already stored)

## 8. Transaction and consistency analysis

Atomic (Postgres): create+reserve; claim; fail+refund; complete+settle
*if no concurrent fail*.

Not atomic: S3 `put` vs document row; document row vs job completed;
in-memory enqueue; temp work dir vs SIGKILL.

Invariant to restore in 10.3B: **a job must not be both settled and
refunded**, and **a terminal `failed` row must not later become
`completed` from a stale in-memory ORM object**.

## 9. Design alternatives

### Option A — Minimal recovery hardening (recommended first)

Safer terminal transitions and credit guards on the current inline
broker. No Redis. No schema required if limited to:

- Complete via `UPDATE … WHERE status='processing'`.
- `settle` no-ops/raises if `refund:{job_id}` exists.
- Heartbeat inside `_run_operation` (optional in the same phase or
  immediately after).
- Structured logs on skip/fail/stale.

**Sufficient** to close F09/F14 without new infrastructure. **Not
sufficient** for F06/F07 orphans.

### Option B — Durable job lifecycle (resume/retry)

Add lease/owner token, `processing → queued` requeue, `max_attempts`,
backoff. Likely schema (`owner_token`, `lease_until`, `max_attempts`).
**Must not precede Option C**: retrying after `_store` already committed
duplicates documents (F11). Defer until result persistence is
idempotent. Not required if product accepts fail+refund as recovery.

### Option C — Result persistence consistency (recommended second)

Stop committing document rows before the job completion transaction.
Record `job_id` (schema **TBD**). Detect orphans (`origin` like
`job:{op}` with no `result_document_ids`). Compensation: expire/delete
orphans; do not delete objects for `processing` jobs.

S3 `put` still cannot join a Postgres commit. Remaining F06 (object
without row) needs a reconciler (P2) or outbox (Option D).

### Option D — Outbox / workflow

Only if A+C leave an unacceptable S3/Postgres split. Adds a table,
uploader path, monitoring, and rollback complexity. **Not recommended
as 10.3B.** Monthly extra cost: **unknown** (no new Render service if
the API process drains the outbox; a worker would be a paid service and
is not justified by this audit).

## 10. Recommended architecture

Keep Render + Postgres + inline broker + S3/R2.

**10.3B (implementation, after approval):** Option A only — conditional
complete, settle-after-refund guard, tests. Optionally heartbeat (P1)
in the same PR if it stays small.

**10.3C:** Option C — defer `_store` commit; job-scoped result identity;
orphan detection. Schema if `job_id` is added.

**Later, only with owner approval:** Option B resume, Option D outbox,
RQ/Redis.

Do **not** split A’s complete predicate from A’s settle-after-refund
guard: shipping one without the other leaves F09 open.

## 11. Measurable reliability requirements

Proposed starting values are **proposals**, not measured SLOs.

| ID | Invariant | Metric | How to measure | Threshold (proposal) | Test | Evidence | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R-OWN-1 | One valid claim | Concurrent `process` completions | Postgres integration | Exactly one `completed` | Two threads / two `process` calls | CI | Eng |
| R-OWN-2 | Duplicate delivery ≠ duplicate logic | Second `process` no-ops | Existing duplicate tests | `rowcount==0` skip | Unit + PG | CI | Eng |
| R-OWN-3 | Crash does not leave two owners | After SIGKILL, at most one claim | Fault test (local/staging) | No double complete | Fault-injection | Staging owner | Eng + owner |
| R-OWN-4 | Live job not stale | Heartbeat age | Clock-controlled unit test | Heartbeat interval **≪** `JOB_STALE_MINUTES` (propose 60s vs 90 min) | Unit | CI | Eng |
| R-REC-1 | Interrupted `processing` leaves terminal or requeued state | Time to terminal/requeue | Settings + cleanup | ≤ `effective_stale_minutes` + cleanup interval (Blueprint: 90 min + 15 min cron) | Unit + cron docs | CI; cron **NOT VERIFIED** in prod | Eng; owner confirms cron |
| R-REC-2 | Retry limits | `attempt` vs max | If Option B | Configurable; start **max_attempts=1** (fail-only) until C lands | Unit | CI | Eng |
| R-REC-3 | No retry storm | Backoff | If Option B | No tight loop | Unit | CI | Eng |
| R-REC-4 | Recovery idempotent | Second stale cleanup | Existing idempotent test | `abandoned_jobs==0` second pass | Unit | CI | Eng |
| R-REC-5 | Terminal not reopened | `failed`/`completed` stay terminal | Race test | Complete `WHERE processing` rowcount 0 after fail | Unit + PG | CI | Eng |
| R-RES-1 | Successful job has result refs | `result_document_ids` vs outputs | Job fixture | IDs match stored outputs **or** empty for text-only ops | Unit | CI | Eng |
| R-RES-2 | Partial persist detectable | Docs with job origin and job `failed` | Query/test | Count ≥ 0 flagged | Unit | CI | Eng |
| R-RES-3 | Orphans reconcilable | Reconcile dry-run | After C | No delete of `processing` results | Unit | CI | Eng |
| R-RES-4 | Retry ≠ duplicate logical docs | If Option B | Same job id / idempotent key | One logical result set | Unit | CI | Eng |
| R-CR-1 | Not both settled and refunded | Ledger keys | Unit + PG concurrent | 0 jobs with both `settle:` and `refund:` | Unit + PG | CI | Eng |
| R-CR-2 | Settle/refund idempotent | Repeat calls | Existing + new reverse-order test | Second call no extra balance change | Unit + PG | CI | Eng |
| R-OBS-1 | Recovery logs | `job_id` + transition | Log assert | No secrets/DSNs | Unit | CI | Eng |

## 12. Prioritized Phase 10.3B roadmap

### 10.3B — P0, one PR (do not split)

| Field | Content |
| --- | --- |
| Priority | **P0** |
| Problem | F09/F14: complete can clobber `failed`; settle can run after refund (`runner.py` 76–82, `ledger.py` 83–111) |
| Proposed | (1) `UPDATE jobs SET completed … WHERE id=? AND status='processing'`; skip settle if rowcount≠1. (2) `settle` returns/raises if `refund:{job_id}` exists. Log `job_id` + reason. |
| Files | `jobs/runner.py`, `billing/ledger.py`, tests under `tests/test_phase92_refunds.py` / new `tests/test_phase103_job_consistency.py` |
| Dependencies | None. No schema. No Redis. |
| Risk | Live thread that lost the race must not charge; user sees `failed` + refund (already stale-cleanup intent) |
| Tests | Settle-after-refund; fail-then-complete race; existing refund/duplicate tests |
| Acceptance | R-CR-1, R-REC-5, R-OWN-1 |
| Complexity | **S** |
| Migration | Not required |
| Rollback | Revert PR; ledger unique keys unchanged |

### 10.3B or immediate follow-up — P1 heartbeat

| Field | Content |
| --- | --- |
| Priority | **P1** |
| Problem | F04: no heartbeat in `_run_operation` |
| Proposed | Periodic `heartbeat_at` during long ops. Proposed interval **60s** (validate; must stay below stale floor). |
| Files | `jobs/runner.py` |
| Dependencies | None |
| Risk | Extra commits; do not heartbeat after terminal |
| Tests | Fake clock: stale cleanup leaves a recently heartbeaten job |
| Acceptance | R-OWN-4 |
| Complexity | **S** |
| Migration | Not required |
| Rollback | Revert |

### 10.3C — P1 result persistence (separate phase, after 10.3B)

| Field | Content |
| --- | --- |
| Priority | **P1** |
| Problem | F06/F07 early `_store` commit/`put` |
| Proposed | Do not `commit` document rows until the job completion transaction. Prefer `job_id` on documents (**schema TBD**). Keep `put` immediately before insert (F06 remains until P2 reconciler). |
| Files | `services/documents.py`, `jobs/runner.py`, possibly `models/entities.py` + Alembic |
| Dependencies | 10.3B first so a lost complete cannot settle after fail |
| Risk | Long transaction holding document inserts; must not commit mid-loop |
| Tests | Crash-after-put (object exists, no row); crash-after-row-without-complete (must not happen if commit deferred); user-visible list has no results for `failed` |
| Acceptance | R-RES-1, R-RES-2 |
| Complexity | **M** |
| Migration | **TBD** (needed if `job_id` column) |
| Rollback | Downgrade only on disposable DB; do not run prod downgrade from an agent |

### Later P2

| Item | Priority | Notes |
| --- | --- | --- |
| Orphan object/document reconciler | P2 | F06 leftover; never delete for `processing` |
| Observability of stale/skip/complete-lost-race | P2 | R-OBS-1 |
| `QUEUED_RECOVERY_LIMIT` loop or raise | P2 | Leave 100 until measured |
| Confirm production cron | P2 | Owner; **NOT VERIFIED** |

### Later P3 (not 10.3B)

Option B resume/retry, Option D outbox, Redis/RQ — **not recommended**
until C exists and product requires resume.

### Phase vs coordinated work

| Theme | How to ship |
| --- | --- |
| Durable terminal-state + credits | **One 10.3B PR** (P0) |
| Heartbeat | Same PR or immediate 10.3B.1 |
| Result persistence | **10.3C**, after 10.3B |
| Fault-injection tests | With each implementation PR; PG race in CI |
| Staging owner verification | **Separate phase** after 10.3B/C CI green; owner-run only |
| Backup / DR (9.15) | **Unrelated**; remains OPEN / INCOMPLETE |

## 13. Focused test strategy (not implemented)

| Category | Where | Evidence |
| --- | --- | --- |
| Lifecycle transitions | Local sqlite | Status predicates |
| Recovery eligibility / stale vs live heartbeat | Local + fake clock | R-OWN-4, R-REC-1 |
| Concurrent ownership / duplicate delivery | **PostgreSQL** CI | Existing + F09 race |
| Retry/backoff | Local, only if Option B | — |
| Partial persistence | Local filesystem storage | F07 |
| Object-storage failure | Unit fake/raise `TransientError` | F13 |
| DB failure | Unit by stubbing `commit` | F12 limited |
| Credit idempotency including settle-after-refund | Local + PG concurrent | R-CR-1/2 |
| Fault-injection SIGKILL | Staging only, owner-approved | Never production |
| Regression extract/merge/delete | Existing job tests | CI |

**Never** run mutating job/credit tests against production. Staging
object-store tests only with a dedicated prefix and owner approval.

## 14. Operational and infrastructure implications

Keep current topology: one API, inline broker, Postgres, S3/R2, 15-minute
cron. Postgres already provides the claim and ledger uniqueness needed
for A. Object storage remains a second system; that is why C cannot be
fully atomic without D.

Redis/RQ: **not required**. Current infrastructure is insufficient only
for cross-store atomicity (S3+PG), which a queue does not fix by itself.

Extra monthly cost of A/C: **unknown** (CPU/DB only; no new service).

## 15. Rollback and migration

10.3B: revert git; no migration.
10.3C: if Alembic added, forward-only on production; test downgrade only
on disposable databases.
Do not restore/PITR to roll back application code.

## 16. Staging and production verification requirements

After implementation (future phases), owner-run **non-production**
checks: interrupt a staging job after claim; after `_store`; confirm
credits and documents. Production: **NOT** part of 10.3A or a default
10.3B agent task.

Labels for this assessment: **STAGING NOT VERIFIED**, **PRODUCTION NOT
VERIFIED**.

## 17. Explicit out of scope

- Implementing any of A–D in this PR
- Redis, RQ, extra workers
- Rate-limit / proxy work (10.2)
- Backup, PITR, R2 restore, DR (Phase 9.15 remains **OPEN** /
  **INCOMPLETE**, production DR **NOT DEMONSTRATED**)
- Changing `JOB_STALE_MINUTES` in Render without owner approval
