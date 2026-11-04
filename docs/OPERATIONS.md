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

Run periodically (cron or worker heartbeat):

```python
from docuflow.jobs.retention import cleanup_abandoned_jobs, cleanup_expired_files
```

Abandoned `processing` jobs older than 45 minutes are marked failed.

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
