# Operations

## Logging

JSON logs when `LOG_JSON=true` or `DOCUFLOW_ENV=production`. Application loggers use the `docuflow.*` namespace. `docuflow.logging.redact` strips passwords, tokens, access keys, signed URLs, and database/Redis URLs. Never print S3 keys or signed URLs.

## Job brokers

Postgres is the source of truth for job status. Redis only delivers `job_id` when `JOB_BROKER=rq`.

### Minimal cost (`JOB_BROKER=inline`) — default

The API thread pool runs jobs. No separate worker is required. `WORKER_CONCURRENCY` is the pool size. Large PDFs can hit the Free web request/CPU budget; expect slower jobs and possible timeouts.

Audited Redis consumers: RQ enqueue (`jobs/broker.py`), the RQ worker process, and `/ready` when `JOB_BROKER=rq`. Sessions, rate limits, and job state do **not** use Redis. With `JOB_BROKER=inline` the API never submits jobs to RQ, so a dedicated worker is idle.

### Worker deployment (`JOB_BROKER=rq`) — scaling option

Do not enable this mode unless `docuflow-worker` is running. Copy the worker from `infra/render.scaling.yaml` and set `JOB_BROKER=rq` on the API. Redis is then required. If no worker has a fresh heartbeat, the API falls back to the inline pool so jobs are not lost. Duplicate `job_id` values do not double-process: the runner claims a row only when `status=queued`.

`WORKER_TIMEOUT_SECONDS` is the RQ job timeout. `WORKER_CONCURRENCY` does not spawn extra RQ processes; each Render worker instance is one RQ worker.

## Graceful shutdown

The worker listens for SIGTERM and requests RQ stop. The API relies on Uvicorn SIGTERM handling. In-flight inline jobs on a Free API die when the instance spins down; remaining `queued` rows stay in Postgres and are kicked again on the next job GET.

## Health

- `GET /health` — liveness only. Render should use this path.
- `GET /ready` — database `SELECT 1`, Redis ping when `JOB_BROKER=rq`, and storage `ping()` (S3 `head_bucket` or a writable local directory). Storage is never reported true without a check. `rq_workers` is informational and does not fail readiness.

## Backups

- PostgreSQL: enable Render point-in-time recovery / daily backups.
- Object storage: enable bucket versioning.
- Redis is expendable. Free Key Value is in-memory and loses the queue on restart. Re-open a `queued` job or create a new job; the API re-enqueues from Postgres.

## Credits

Balances are integers. `available = balance - reserved`. Ledger keys:

| Action | Idempotency key |
| --- | --- |
| Reserve | `reserve:{job_id}` |
| Settle | `settle:{job_id}` |
| Refund | `refund:{job_id}` |

Failed and cancelled jobs refund the reservation without changing `balance`.
Job failure status and the refund row are committed in the same database
transaction. A second refund for the same job is a no-op. A settled job is
never refunded. Missing or partial reserved balances release only what is
still reserved. Cleanup also recovers terminal jobs whose fail commit landed
historically without a refund.

## Retention

Cleanup is scheduled. It does not run on HTTP requests.

- Render Cron `docuflow-cleanup` is the production scheduler (`python -m docuflow.cleanup` every 15 minutes, billed only while running).
- The API in-process interval is **off** in the default Blueprint (`CLEANUP_INTERVAL_SECONDS=0`) so cron is the single cleaner. Set `900` only if you omit the cron.
- Overlapping runs take a PostgreSQL-backed `cleanup_leases` row (`name`, owner `token`, `locked_until` / `lease_until`, `acquired_at`, `updated_at`). Acquisition is an atomic `UPDATE` of an expired or unowned row. Session-level advisory locks are not used; they are unsafe with connection pooling. The owner renews the lease between cleanup stages; a process that loses ownership stops remaining work. Only the current owner token can renew or release. After a crash the lease expires and another process can reclaim it.
- A job is abandoned only when `status=processing` and `heartbeat_at` (or `started_at` if no heartbeat) is older than `JOB_STALE_MINUTES`, which is never below the worker timeout plus grace. Fail + refund is one transaction.
- Expired uploads/results (`FILE_RETENTION_HOURS` / `RESULT_RETENTION_HOURS`) are marked deleted, then object storage is removed through `storage_deletions`. Rows left `in_progress` past `STORAGE_DELETE_LEASE_MINUTES` are reclaimed. Completion and failure updates require the claiming owner token, so an expired worker cannot overwrite a newer owner. Object delete is idempotent (already-gone is success). Completed rows are not processed again. Failed object deletes never undelete the row.

```
python -m docuflow.cleanup
```

## Incidents

1. Check `/health` then `/ready`. A `degraded` ready payload names the failed dependency without secrets.
2. Inspect failed jobs in `/admin`.
3. If jobs stay `queued`, confirm `JOB_BROKER=inline` or that the paid worker is running.
4. Confirm S3 credentials in the dashboard without printing them.
5. Refund or retry from admin only with a ledger reason.

## Dependency checks

```bash
uv run pip-audit || true
pnpm --filter web audit || true
```

`pip-audit` is not bundled by default; install it in CI when you enable scheduled scans.
