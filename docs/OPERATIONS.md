# Operations

## Logging

JSON logs when `LOG_JSON=true` or `DOCUFLOW_ENV=production`. Application loggers use the `docuflow.*` namespace. `docuflow.logging.redact` strips passwords, tokens, access keys, signed URLs, and database/Redis URLs. Never print S3 keys or signed URLs.

## Job brokers

Postgres is the source of truth for job status. Redis only delivers `job_id` when `JOB_BROKER=rq`.

### Minimal cost (`JOB_BROKER=inline`)

The API thread pool runs jobs. No separate worker is required. `WORKER_CONCURRENCY` is the pool size. Large PDFs can hit the Free web request/CPU budget; expect slower jobs and possible timeouts.

### Worker deployment (`JOB_BROKER=rq`)

The API enqueues to Redis. `docuflow-worker` must be running with the same `DATABASE_URL`, `REDIS_URL`, `RQ_QUEUE_NAME`, and S3 credentials. If no worker has a fresh heartbeat, the API falls back to the inline pool so jobs are not lost. Duplicate `job_id` values do not double-process: the runner claims a row only when `status=queued`.

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

## Retention

Cleanup is scheduled. It does not run on HTTP requests.

- Render Cron `docuflow-cleanup` runs `python -m docuflow.cleanup` every 15 minutes (billed only while running).
- The API (inline) and the RQ worker also start an in-process interval thread (`CLEANUP_INTERVAL_SECONDS`, default 900). Set it to `0` to rely on cron only.
- Overlapping runs take a lease (Postgres advisory lock, or `cleanup_leases` on SQLite) so the same reservation is not refunded twice. Ledger refund keys remain idempotent.
- A job is abandoned only when `status=processing` and `heartbeat_at` (or `started_at` if no heartbeat) is older than `JOB_STALE_MINUTES`, which is never below the worker timeout plus grace.
- Expired uploads/results (`FILE_RETENTION_HOURS` / `RESULT_RETENTION_HOURS`) are marked deleted, then object storage is removed through a durable outbox with bounded backoff. Failed object deletes never undelete the row.

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
