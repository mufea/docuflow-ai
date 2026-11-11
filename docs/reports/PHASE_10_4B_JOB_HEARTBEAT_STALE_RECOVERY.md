# Phase 10.4B — Job heartbeat and stale-processing recovery

Implementation of the Phase 10.4A recommended design. No schema, Redis,
or resume.

## Mechanism

- `touch_processing_heartbeat(job_id) -> bool` uses a dedicated
  `session_factory()` session:
  `UPDATE jobs SET heartbeat_at=now() WHERE id=:id AND status='processing'`.
  Returns `rowcount==1`. Database errors propagate.
- `ProcessingHeartbeat` runs that helper from a daemon thread (own session
  per tick) during `_run_operation`, interval `JOB_HEARTBEAT_SECONDS`
  (default 60; `0` disables the timer). Stop/`join` in `finally`.
- Progress 25/80 uses `UPDATE … WHERE status='processing'` on the worker
  session **before** `store_result`. Heartbeat is never assigned on that
  ORM object, so a later 10.3C commit cannot dirty-write liveness onto a
  failed row.
- If a heartbeat returns false after the engine call, the worker raises
  `JobStateError` and skips `store_result` / complete / settle.
  `fail_job_and_refund` is a no-op when cleanup already claimed the row.

## Stale detection

`_fail_stale_jobs` still selects processing rows older than
`effective_stale_minutes()`. The fail claim now includes
`stale_processing_clause(cutoff)` so a concurrent fresh heartbeat cannot
be failed.

Fencing is `status='processing'`. No owner token. Resume and automatic
retry remain out of scope (no `job_id` on result documents).

## Credits

Unchanged: reserve / settle / `refund:{job_id}` / account `FOR UPDATE`.
Stale fail still refunds once. Lost-ownership complete does not settle.

## Operational notes

- Cron `*/15` and production heartbeat interval: **NOT VERIFIED**.
- SIGKILL after claim still waits for stale+cron.
- Heartbeat is liveness of database writes, not engine progress.
- Staging / production: **NOT VERIFIED**.

## GitHub merge evidence (post-merge addendum)

Recorded by Phase 10.4B-R2. Does not add staging or production
verification.

| Item | Value |
| --- | --- |
| PR | [#65](https://github.com/mufea/docuflow-ai/pull/65) **MERGED** |
| PR head | `f1802a06461d1e0c6138330e5a40fae8ec09b10f` |
| Merge commit / `origin/main` | `17dfe9c9d27420b0d6999e75dc1c09e6b9da4bef` |
| Merged at | `2026-11-11T07:47:14Z` / **11 Nov 2026, 14:47 Asia/Jakarta** |
| PR CI | [42976568192](https://github.com/mufea/docuflow-ai/actions/runs/42976568192) **SUCCESS** |
| Main push CI | [42982048354](https://github.com/mufea/docuflow-ai/actions/runs/42982048354) **SUCCESS** |
| Main CI completed | `2026-11-11T07:49:08Z` / **11 Nov 2026, 14:49 Asia/Jakarta** |

**MERGED** is not **DEPLOYED**. CI **SUCCESS** is not **STAGING VERIFIED**.
