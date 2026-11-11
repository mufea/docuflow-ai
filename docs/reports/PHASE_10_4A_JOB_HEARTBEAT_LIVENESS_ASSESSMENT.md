# Phase 10.4A — Job heartbeat, liveness, and stale-recovery assessment

Documentation-only. No application, schema, or infrastructure change.

Time: **11 Nov 2026, 09:04 Asia/Jakarta (WIB)**.

## 1. Baseline and audit environment

| Item | Value |
| --- | --- |
| Mandatory baseline | `4948c79611dbe2f9d53b6cbc5b84b1cba25385a1` |
| `origin/main` | same (PR [#58](https://github.com/mufea/docuflow-ai/pull/58) merge) |
| Audit branch | `audit/phase-10-4a-job-heartbeat-liveness` |
| Production DSN | **not used** |
| Staging / production | **NOT VERIFIED** |

HEAD at inspection was `d0e5631` on the merged 10.3D branch. Working tree
was clean. This branch was created from `origin/main`. No reset.

Phase 10.3A already recorded F04 (no heartbeat in `_run_operation`) and
the stale-vs-live race. This report does not repeat that audit; it
assesses current code **after** 10.3B/C and scopes **10.4B**.

## 2. Architecture overview

Production (Blueprint): FastAPI + inline `ThreadPoolExecutor`
(`WORKER_CONCURRENCY=2`) + PostgreSQL. `CLEANUP_INTERVAL_SECONDS=0` on
the API. Render Cron `docuflow-cleanup` runs
`python -m docuflow.migrate && python -m docuflow.cleanup` on
`*/15 * * * *`. Cron execution in production is **NOT VERIFIED**.

Job liveness is a **timestamp on the job row**, not a worker identity:

- Claim: `UPDATE jobs SET status='processing', heartbeat_at=now() … WHERE status='queued'` (`runner.py`).
- Two later ORM writes: `progress=25` / `80` plus `heartbeat_at` on the **same** worker session, then `commit()`.
- Stale fail: `_fail_stale_jobs` selects `processing` rows whose
  `heartbeat_at` (else `started_at`) is older than
  `effective_stale_minutes()`, then `fail_job_and_refund(…, expected_statuses=('processing',))`.

RQ `Worker.last_heartbeat` (90s) is **enqueue routing only**. It is not
the job-row heartbeat. Production default is `JOB_BROKER=inline`.

Preserved 10.3B/C invariants (do not regress in 10.4B):

- Queued claim is conditional.
- Complete is `WHERE status='processing'`.
- Settle refuses `refund:{job_id}` under account `FOR UPDATE`.
- Result documents `flush()` only; one final commit with complete+settle.

## 3. Current heartbeat lifecycle

| Location | Mechanism | Session | Commits pending result rows? |
| --- | --- | --- | --- |
| Claim (`process`) | SQL `UPDATE … WHERE queued` sets `heartbeat_at` | Worker session | No (before execute) |
| After download (`_execute`) | ORM `job.heartbeat_at`; `session.commit()` | Worker session | No (before `_run_operation`) |
| After `_run_operation` | Same ORM + `commit()` at progress 80 | Worker session | No (before `store_result`) |
| Inside `_run_operation` | **None** | — | — |
| During `store_result` loop | **None** | — | A main-session commit here **would** persist flushed documents (10.3C) |
| After complete / fail | None; `process()` returns | — | — |

`_run_operation` is a blocking call into PDF/OCR/conversion/AI. There is
no periodic touch. A healthy job whose engine call lasts longer than the
stale window looks abandoned (10.3A F04; still true).

Heartbeat exceptions: the 25/80 `commit()` failures abort `process()`
and take the generic fail+refund path. There is no isolated heartbeat
error handling.

Heartbeat after terminal: nothing continues after `process()` returns.
A **late** 25/80 ORM `commit()` can still write `heartbeat_at`/`progress`
on a row cleanup already marked `failed`, because those assignments are
**not** `WHERE status='processing'`. That does not flip status back to
`processing` (SQLAlchemy updates dirty columns only). It is not a
liveness signal cleanup uses, because cleanup selects `status=processing`.

Independent session: **feasible**. `JobRunner` already has
`session_factory`. `DECISIONS.md` notes SQLAlchemy sessions are not
thread-safe; a **second** session is the way to heartbeat from another
thread without sharing the worker session.

Cleanup `LeaseGuard.heartbeat()` renews the **cleanup lease row**, not
job `heartbeat_at`.

## 4. Stale detection behavior

`effective_stale_minutes(settings)` =
`max(JOB_STALE_MINUTES, max(15, ceil((WORKER_TIMEOUT_SECONDS+119)/60)))`.
Defaults: 90 minutes (timeout 300s → floor 7, so 90). Tests:
`test_effective_stale_minutes_never_below_worker_timeout`.

`_fail_stale_jobs`:

1. `SELECT` processing rows with `heartbeat_at < cutoff` (or null
   heartbeat and `started_at < cutoff`).
2. Optionally skip if in-memory beat is now ≥ cutoff (**does not
   `refresh()`**; uses the SELECT snapshot).
3. `fail_job_and_refund` `UPDATE … WHERE status='processing'` **without**
   a heartbeat-age predicate.

A heartbeat timestamp is **last successful write of `heartbeat_at`**.
It is not proof the engine is making progress. A spinning thread that
still writes beats looks live. A live merge that never writes looks
dead.

Cron: Blueprint `*/15`. API in-process scheduler off (`CLEANUP_INTERVAL_SECONDS=0`).
Effective delay after last beat: stale minutes **plus** cron latency
(up to ~15 min if cron runs). Production cron: **NOT VERIFIED**.

## 5. Ownership and race analysis

There is **no** job owner token, lease, or fencing id. Ownership is
“the row is `processing`.” 10.3B complete and fail already use that
predicate. Heartbeat at 25/80 does **not**.

| Situation | Distinguishable today? |
| --- | --- |
| Actively running worker | Only if it recently wrote `heartbeat_at` |
| Slow but healthy `_run_operation` | **No** — looks stale after the window |
| Stalled worker (no DB writes) | Yes, after stale cutoff |
| Terminated worker (SIGKILL) | Same as stalled; remains `processing` until cleanup |
| Lost DB connectivity | No beats; looks stale; worker may still run locally |
| Worker continues after stale fail | Yes for **complete** (10.3B/C: `claimed=False`, rollback, no settle). Heartbeat ORM commit can still touch the failed row’s `heartbeat_at` |

A lease/owner/fencing token is **not required for 10.4B** if heartbeat
and stale-fail both use `WHERE status='processing'` (and stale-fail also
requires an old heartbeat at claim time). Tokens become useful when
**retry/resume** must ignore a late original worker (out of scope).

Lost-ownership signal without schema: heartbeat or complete
`rowcount != 1`. The worker cannot preempt a blocking engine call; it
can skip `store_result` / complete afterward (already true for complete).

## 6. PostgreSQL concurrency

Worker heartbeat (today): `UPDATE` of dirty columns by primary key
(implicit). Cleanup fail: `UPDATE … WHERE status='processing'`. Row lock
serializes the two writes. Complete vs cleanup is already covered by
10.3B (`WHERE processing`) and PG tests.

TOCTOU in `_fail_stale_jobs`: SELECT by old heartbeat, then fail by
status only. A worker can refresh `heartbeat_at` after the SELECT and
still be failed. 10.4B should fail with
`WHERE status='processing' AND heartbeat still old` (same cutoff).

SQLite tests are **not** evidence of this locking.

## 7. Failure scenario matrix

| # | Scenario | Current behavior | 10.3B/C help? | 10.4B needed? |
| --- | --- | --- | --- | --- |
| 1 | Heartbeat vs stale cleanup | Cleanup may still fail a job that beat after SELECT | Partial (fail is conditional on `processing`) | Yes — heartbeat predicate on fail; conditional heartbeat |
| 2 | Complete vs stale cleanup | At most one terminal; no settle after refund | **Yes** (tested) | No (preserve) |
| 3 | Fail/refund vs late complete | Late complete `claimed=False`; result rows rolled back | **Yes** (tested) | No (preserve) |
| 4 | DB outage during heartbeat | 25/80 commit raises → job fail+refund if session recovers; else row stays `processing` until stale | Indirect | Isolated heartbeat errors |
| 5 | Long op > stale window | Live work failed as `timeout` | No | Periodic beat during the op |
| 6 | SIGKILL just after claim | Stays `processing` until stale+cron | Intentional (no resume) | Heartbeat does not change this |

## 8. Existing test coverage

| Area | Tests |
| --- | --- |
| Stale floor vs worker timeout | `test_effective_stale_minutes_never_below_worker_timeout` |
| Fresh heartbeat not abandoned | `test_recent_heartbeat_is_not_abandoned` |
| Stale fail+refund idempotent | `test_stale_job_cleanup_is_idempotent`, `test_phase92_refunds` |
| Restart does not requeue `processing` | `test_recovery_skips_processing_jobs_and_cleanup_fails_stale` |
| Complete vs fail, settle vs refund (PG) | `test_postgres_complete_versus_fail_*`, `test_postgres_concurrent_refund_and_settle_*` |
| Lost complete rolls back result docs | 10.3C unit + PG |
| RQ worker heartbeat (enqueue only) | `test_stale_rq_heartbeat_is_not_active` |
| Scheduler disabled at interval 0 | `test_cleanup_scheduler_disabled_when_interval_is_zero` |

## 9. Missing regression tests (for 10.4B)

1. Periodic / interval heartbeat during a long `_run_operation` (fake clock or injected sleeper).
2. Heartbeat `UPDATE … WHERE status='processing'`: `queued`/`failed`/`completed` → `rowcount=0`.
3. Heartbeat must **not** `commit()` the worker session after `store_result(commit=False)`.
4. PG: concurrent heartbeat vs stale fail — winner consistent with heartbeat age at claim.
5. Stale fail `WHERE processing AND heartbeat_at < cutoff` does not fail a just-touched job.
6. Heartbeat `rowcount=0` after cleanup: worker skips settle (already) and does not write heartbeat onto the failed row.
7. SQLite must not be labeled as PG lock proof.

## 10. Design alternatives

| Option | Complexity | Writes | Pool | Race safety | Inline / RQ | Schema | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. Periodic beat, **dedicated session** | S | 1/interval/job | +1 conn per in-flight (≤2) | Good if `WHERE processing` | Yes / Yes (`JobRunner`) | None | Does not commit 10.3C rows |
| B. Conditional `UPDATE heartbeat_at WHERE processing` | S | Same | n/a | Prevents beating terminal rows | Yes | None | Required either way |
| C. Lease + owner token | M | Renewals | Extra | Strong | Yes | **Yes** | Not needed until resume |
| D. Fencing / attempt token | M | Low | n/a | Strong vs late worker | Yes | Likely | For retry, not 10.4B |
| E. Lost-ownership abort | S | 0 extra | n/a | Uses `rowcount` from A/B | Yes | None | Cannot stop a blocking engine call |
| Main-session ORM beat (today) | — | 25/80 only | 0 | Weak; can dirty-write failed rows; **cannot** run during store_result | Yes | None | Insufficient |
| Redis/RQ required | — | — | — | — | No | — | Rejected |

## 11. Recommended minimal Phase 10.4B

One PR, no schema, no Redis:

1. **`touch_processing_heartbeat(job_id) -> bool`**. Dedicated
   `session_factory()` session.
   `UPDATE jobs SET heartbeat_at=now() WHERE id=:id AND status='processing'`.
   Return `rowcount==1`. Log skip. Do not swallow DB errors as success.

2. **Use it during `_run_operation`.** Smallest complete form: a
   worker-side timer thread with **its own** session (addresses
   `DECISIONS.md` thread-safety), interval **60s** (much less than 90 min
   stale and 15 min cron). Stop/`join` in `finally`. If `touch` returns
   false, skip `store_result` after the engine returns.

3. **Replace 25/80 ORM heartbeat commits** with the same helper so all
   beats are conditional.

4. **Tighten stale claim** so `_fail_stale_jobs` / `fail_job_and_refund`
   for timeouts uses `WHERE status='processing' AND (heartbeat_at <
   :cutoff OR (heartbeat_at IS NULL AND started_at < :cutoff))`.

5. **Tests** in §9, including one PostgreSQL concurrency test.

Keep progress 25/80 as progress updates only if they stay on the worker
session **before** result `flush()`. Do not `commit()` that session
during `store_result`.

Do **not** add owner_token, resume, retry, or orphan GC.

## 12. Explicit non-goals

- Resume `processing` or automatic retry (needs job-scoped result
  identity first; 10.3C deferred DB commit but did not add `job_id` on
  documents; retry would still duplicate S3 objects).
- Redis, RQ requirement, extra Render worker.
- Schema migration.
- Orphan object deletion.
- Shortening `JOB_STALE_MINUTES` without heartbeat (would fail live work).
- Staging/production deploy.

## 13. Operational risks and unverified assumptions

- Cron `*/15` in production: **NOT VERIFIED**.
- Single blocking engine call still cannot be interrupted; worst-case
  fail of live work is `interval` after the last successful beat, plus
  cron lag, only if beats stop.
- Timer thread + extra session: must always stop in `finally`.
- Heartbeat is not progress proof.
- SIGKILL still waits for stale+cron (product choice until resume exists).

## 14. Phase 10.4B acceptance criteria

- [ ] Heartbeats use a DB predicate `status='processing'` (not ORM-only).
- [ ] Heartbeat session is not the worker session that holds uncommitted result rows.
- [ ] A `processing` job with beats inside the stale window is not failed.
- [ ] A job already `failed`/`completed` does not accept heartbeat (`rowcount=0`).
- [ ] Stale fail cannot beat a concurrent fresh heartbeat (PG test).
- [ ] 10.3B complete/settle and 10.3C deferred documents still pass.
- [ ] No migration, Redis, or Render change.
- [ ] Staging / production: **NOT VERIFIED**.
