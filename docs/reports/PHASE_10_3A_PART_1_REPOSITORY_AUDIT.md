# Phase 10.3A Part 1 — Repository audit and failure analysis

Read-only working report for durable job recovery and result-persistence
consistency. **Not** an implementation. **Not** staging or production
verification.

Audit time: **10 Nov 2026, 22:14 Asia/Jakarta (WIB)**.

## 1. Repository baseline and working tree

| Item | Value |
| --- | --- |
| Expected `origin/main` | `2447ac516d29cfeb7d3297cfcefd6a9591343694` |
| Actual `origin/main` | `2447ac516d29cfeb7d3297cfcefd6a9591343694` |
| Match | **Yes** (PR #54 merge, 10 Nov 2026, 21:28 Asia/Jakarta) |
| Audit branch | `audit/phase-10-3a-durable-job-recovery` (from `origin/main`) |
| Working tree | clean at checkout |
| Application edits this part | **None** |

Prior inspection on `feat/phase-10-2-runtime-reliability-remediation`
(`9860b07`) was not used as the audit baseline; findings below are from
`2447ac5`.

## 2. Architecture overview

Default stack (Blueprint, not live-probed): one uvicorn API process,
`JOB_BROKER=inline`, `WORKER_CONCURRENCY=2` (in-process thread pool),
Postgres job rows as source of truth, S3/R2 for objects, cleanup cron
`*/15` with API `CLEANUP_INTERVAL_SECONDS=0`. RQ exists in code but is
unused while `JOB_BROKER=inline`.

```
Client POST /v1/jobs
  → JobService.create (queued + reserve, one DB commit)
  → InlineBroker.enqueue (in-memory _inflight + thread)
  → JobRunner.process
       UPDATE jobs SET processing WHERE queued  (commit)
       download → operate → store_result* (each commits)
       SET completed + settle  (one DB commit)
  On crash of processing: wait JOB_STALE_MINUTES then fail+refund
  On restart: recover_queued_jobs re-enqueues status=queued only
```

\* `store_result` / `_store` is a **separate** DB commit and a **separate**
object-store write. It is not in the completion transaction.

## 3. Job lifecycle

Implemented statuses: `queued` (insert), `processing` (claim),
`completed` (runner), `failed` (runner or stale cleanup), `cancelled`
(queued only).

```
create  →  queued  →  processing  →  completed
                      ↘ failed (exception or stale timeout)
queued  →  cancelled (user cancel only)
```

There is **no** `processing → queued` recovery transition. `Job.attempt`
is incremented on claim (`runner.py` 59) and is **not** read for retry.

| Step | Function | Persist? |
| --- | --- | --- |
| Create + reserve | `JobService.create` 23–65 | Yes (`session.commit` 63) |
| Enqueue | `InlineBroker.enqueue` 30–35 | No (`_inflight` set) |
| Claim | `JobRunner.process` 52–63 | Yes (atomic `UPDATE … WHERE status=queued`) |
| Heartbeat 25% / 80% | `_execute` 130–136 | Yes (intermediate commits) |
| Store each result | `DocumentService._store` 316–352 | Yes (own commit 350) **and** object `put` 330 |
| Complete + settle | `process` 76–82 | Yes (one commit 82) |
| Fail + refund | `fail_job_and_refund` 23–72 | Yes (status claim + `refund:{job_id}`) |
| Cancel queued | `JobService.cancel` 78–86 | Yes |
| Recover queued | `recover_queued_jobs` 19–45 | Re-enqueue only |
| Stale processing | `_fail_stale_jobs` 139–186 | Fail + refund; no retry |

HTTP `GET /v1/jobs/{id}` re-enqueues if still `queued` (`jobs.py` 79–80).

## 4. Crash recovery analysis

**Graceful shutdown (SIGTERM / lifespan):** `CleanupScheduler.stop` then
`InlineBroker.shutdown(wait=True)` (`main.py` 57–62, `broker.py` 46–48).
In-flight threads may finish a claim. SIGKILL does **not** run this path.

**After claim, process gone:** row stays `processing`.
`recover_queued_jobs` explicitly does not touch those rows (docstring
25–29). Distinguishing live vs abandoned is **time-based**:
`heartbeat_at` (else `started_at`) older than `effective_stale_minutes`
(default `max(90, floor from WORKER_TIMEOUT_SECONDS)`, `retention.py`
54–56). Production cron every 15 minutes; in-process scheduler off.

**Automatic vs manual:** queued recovery is automatic on API start (cap
100). Processing recovery is automatic **fail+refund** after the stale
window, not resume. No operator action in code; delay is the stale
threshold plus cron lag.

**Two workers, same job:** claim `rowcount != 1` skips (`runner.py`
64–66). Duplicate enqueue of `queued` is therefore safe. `_inflight`
is process-local and lost on crash.

**Retry / backoff:** none for `processing`. User must create a new job.
`attempt` unused beyond increment.

Answers:

1. Exit after claim: stays `processing` until stale fail+refund.
2. Crash during processing: same; temp `work_directory` is not cleaned
   on SIGKILL (`workdir.py` 23–24 `finally` does not run).
3. Exit after output generation: if `_store` already committed, orphan
   documents/objects; job still `processing` then later `failed`.
4. Recover processing after restart? **No resume.** Only fail later.
5. Automatic fail after stale window (if cron/scheduler runs). Cron
   actually running in production is **NOT VERIFIED** this part.
6. Active vs abandoned: heartbeat/started vs cutoff only. A live job
   with a heartbeat gap longer than the stale window looks abandoned.
7. Duplicate execution: prevented by queued claim. **CONFIRMED**.
8. Retry limits/backoff: **not implemented** for processing.
9. Graceful vs abrupt: graceful waits on the pool; SIGKILL does not.

## 5. Result persistence sequence

For operations that emit files (`merge`, `split`, …):

1. Local output in `work_directory` (`_run_operation`).
2. `storage.put` — object exists **before** any document row
   (`documents.py` 330 then 337–350).
3. `session.add(Document)` + `session.commit()` — document row durable;
   `origin=f"job:{operation}"` (not job id).
4. IDs collected on the in-memory `Job`; **not committed** until step 6.
5. `job.status = "completed"`; `CreditService.settle`; `session.commit()`.

`extract_text` / `ocr` / AI ops return no files (`return []`), so steps
2–3 are skipped; payload sits in memory until step 5.

No reconciliation job maps orphan `Document` rows or S3 keys back to
failed jobs. `result_document_ids` is written only in the completion
commit. Failed jobs do not point at results that already landed.

## 6. Credit ledger analysis

Keys (`ledger.py`): `reserve:{job_id}`, `settle:{job_id}`,
`release-settle:{job_id}`, `refund:{job_id}`. Unique constraint
`uq_ledger_idempotency` (`entities.py` 155).

| Check | Code | Tests |
| --- | --- | --- |
| Duplicate reserve | `reserve` 69–71 early return | `test_idempotent_duplicate_reserve` |
| Duplicate refund | `refund_reservation` 127–128 + nested IntegrityError 147–149 | `test_duplicate_refund_is_idempotent`, postgres concurrent test |
| Refund after settle | skipped if `settle:{job_id}` exists (125–126) | `test_refund_does_not_run_after_settle` |
| Fail+refund atomic with job status | `fail_job_and_refund` UPDATE then refund then one commit | `test_job_failure_and_refund_are_atomic` |
| Duplicate settle | `settle` 86–87 returns if `settle:{job_id}` exists | implied by skip; **no test found for settle after refund** |
| Settle after refund | `settle` does **not** check `refund:{job_id}` | **gap** |

Create+reserve share one commit (`jobs.py` 60–63). Complete+settle share
one commit (`runner.py` 76–82). `settle` itself does not `commit`.

`refund_failed_jobs` defaults True (`plans.py` 82).

## 7. Transaction boundaries

| Boundary | Atomic? | Systems |
| --- | --- | --- |
| Create job + reserve | Yes (one Postgres commit) | Postgres |
| Claim queued→processing | Yes (single UPDATE) | Postgres |
| Heartbeat 25% / 80% | Yes (own commits) | Postgres |
| Object `put` vs document row | **No** | S3/R2 then Postgres |
| Document row vs job completed | **No** | two Postgres commits |
| Job completed vs settle | Yes (same commit) | Postgres |
| Fail status vs refund | Yes (`fail_job_and_refund`) | Postgres |
| Enqueue / `_inflight` | N/A (memory) | Process |
| Temp work dir vs anything durable | N/A | Local disk |

Atomicity is **not** guaranteed across object storage and Postgres, nor
across `_store.commit` and completion commit.

## 8. Failure scenario matrix

Expected behavior = durable job row consistent with credits and with any
result objects; no silent double-charge; no unbounded `processing`.

| ID | Class | Current behavior | Protection | Gap |
| --- | --- | --- | --- | --- |
| **F01** crash before claim | **VERIFIED SAFE** | Stays `queued`; start re-enqueues (cap 100) | Claim `WHERE queued` | Jobs beyond 100 wait for GET or later start |
| **F02** crash just after claim | **VERIFIED UNSAFE** (stuck until stale) | `processing` until cleanup | Stale fail+refund | No resume; delay ~90 min + cron |
| **F03** crash during download | **VERIFIED UNSAFE** (same as F02) | Temp file lost; no result rows | work_directory on graceful exit only | SIGKILL temp leftovers; job stuck then fail |
| **F04** crash during PDF/AI | **VERIFIED UNSAFE** (same as F02) | No heartbeat during `_run_operation` 152–266 | Stale window 90 min | Live job can look stale if op > window |
| **F05** crash after output, before `_store` | **VERIFIED UNSAFE** (same as F02) | Local outputs deleted on graceful `finally`; SIGKILL may leave temps | work_directory | No durable result; job fail later |
| **F06** object put OK, DB document fail | **VERIFIED UNSAFE** | Orphan object; exception → fail+refund | None for object | No orphan reconciler |
| **F07** document commit OK, job complete fail/crash | **VERIFIED UNSAFE** | User-visible Document rows; job later `failed`+refund; `result_document_ids` empty | Retention expiry | Duplicate outputs if user retries; credits not double-settled |
| **F08** job complete vs settle | **VERIFIED SAFE** | Same session commit (`runner.py` 76–82) | One transaction | If settle raises, rollback then fail+refund |
| **F09** stale cleanup vs live job | **VERIFIED UNSAFE** (race) / overlap **POTENTIAL RISK** | Complete path is unconditional ORM assign, **not** `UPDATE WHERE processing`. `settle` ignores `refund:{job_id}` | Cleanup uses `WHERE processing`; heartbeat 25/80 | Cleanup-then-complete can fail+refund then overwrite to completed and settle |
| **F10** duplicate delivery | **VERIFIED SAFE** | Second `process` skips if not queued | Claim rowcount; tests `test_duplicate_process_does_not_double_charge`, `test_duplicate_recovery_does_not_double_charge` | `_inflight` not durable (unnecessary once claimed) |
| **F11** retry after partial persist | **NOT APPLICABLE** (no processing retry) / **VERIFIED UNSAFE** if user creates a new job | New job + new `put` keys (`uuid4`) | New storage keys | Duplicate documents; no link to failed job |
| **F12** DB down during processing | **POTENTIAL RISK** | Heartbeat/complete/`_fail` commits can fail; row may remain `processing` | Stale cleanup later | Cleanup also needs DB; **NOT VERIFIED** under real outage |
| **F13** object store down | **CONFIRMED** (handled as error) | `TransientError` from s3.py 136–142; `_fail` refunds | DocuflowError path | Prior `_store` successes in the same job remain (partial F07) |
| **F14** duplicate refund/settle | **VERIFIED SAFE** for refund duplicates and refund-after-settle; **VERIFIED UNSAFE** for settle-after-refund | Unique ledger keys; refund checks settle; settle does not check refund | Tests for refund idempotency | Missing settle-after-refund guard (feeds F09) |
| **F15** SIGKILL / no graceful shutdown | **VERIFIED UNSAFE** | Same as F02–F07 depending on timing; `shutdown(wait=True)` skipped | Stale fail+refund | Inherent to inline-in-process |

Do not treat “exception is caught” as safe: `_fail` only runs if the
process still lives.

## 9. Confirmed reliability gaps

1. **No resume of `processing` after crash** — only delayed fail+refund.
2. **`_store` commits (and `put`s) before job completion** — F06/F07 orphans.
3. **Completion is not a conditional status update** — can clobber a
   concurrent stale `failed` (F09).
4. **`settle` does not refuse `refund:{job_id}`** — F14 reverse order.
5. **No heartbeat during `_run_operation`** — F04/F09 window.
6. **`Job.attempt` unused; no bounded retry** — by design today, so
   partial results are not overwritten by an automatic second run, but
   user retry duplicates.
7. **No orphan object/document reconciler.**
8. **Queued recovery cap 100** — remainder wait GET or next boot.

Redis/RQ are **not** required to close these gaps; they are Postgres
transaction and status-predicate issues plus object-store ordering.

## 10. Unverified assumptions

- Production cleanup cron currently running: **NOT VERIFIED**.
- Production `JOB_STALE_MINUTES` / `CLEANUP_INTERVAL_SECONDS` still match
  Blueprint: **NOT VERIFIED** (source says 90 and 0).
- F09 overlap occurring in production: **NOT VERIFIED** (90 min makes it
  unlikely for typical PDFs).
- SQLite `FOR UPDATE` strength vs Postgres: refund concurrency tests
  exist under postgres integration; production uses Postgres.
- Staging/production crash behavior: **NOT VERIFIED**.

## 11. File / function references

- `src/docuflow/services/jobs.py` — `create` 23–65, `cancel` 78–86
- `src/docuflow/api/routes/jobs.py` — `create_job` 48–67, `get_job` 70–82
- `src/docuflow/jobs/broker.py` — `InlineBroker` 21–48
- `src/docuflow/jobs/runner.py` — `process` 49–91, `_execute` 113–150
- `src/docuflow/jobs/recovery.py` — `recover_queued_jobs` 19–45
- `src/docuflow/jobs/retention.py` — `effective_stale_minutes` 54–56,
  `_fail_stale_jobs` 139–186
- `src/docuflow/jobs/refunds.py` — `fail_job_and_refund` 23–72
- `src/docuflow/jobs/scheduler.py` — `start` 30–45
- `src/docuflow/main.py` — lifespan 54–62
- `src/docuflow/services/documents.py` — `_store` 316–352
- `src/docuflow/storage/s3.py` — `put` 127–143
- `src/docuflow/billing/ledger.py` — `reserve` 56–81, `settle` 83–111,
  `refund_reservation` 113–150
- `src/docuflow/models/entities.py` — `Job` 112–136, `CreditLedger` 153–155
- `src/docuflow/pdf/workdir.py` — `work_directory` 15–24
- `infra/render.yaml` — uvicorn start 50; `JOB_STALE_MINUTES` 122–127; cron 135–141

## 12. Questions Part 2 must resolve

1. Minimum change to make completion/settle conditional on
   `status=processing` (close F09/F14 reverse settle) without Redis?
2. Minimum change so result `put`+document row commit with (or after,
   and rolled back with) job completion — same transaction vs outbox?
3. Is delayed fail+refund the accepted recovery objective, or is resume
   of `processing` required? Resume needs F07 idempotency first.
4. Should heartbeat run inside `_run_operation`, and what interval?
5. Acceptance tests: crash-after-`_store`, settle-after-refund, complete
   vs stale-fail race — which are in scope for 10.3A implementation?
6. Orphan document/object cleanup: in scope or deferred?
7. Queued recovery cap of 100: leave, raise, or loop?

Part 2 should produce a measurable plan. This part does not authorize
implementation.
