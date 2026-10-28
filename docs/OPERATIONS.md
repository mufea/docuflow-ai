# Operations

## Logging

JSON logs when `LOG_JSON=true` or `DOCUFLOW_ENV=production`. Application loggers use the `docuflow.*` namespace.

## Worker sizing

Start with `WORKER_CONCURRENCY=2` on a 1 GB worker. PDF rasterization and OCR are CPU/memory heavy. Increase only after measuring. `WORKER_TIMEOUT_SECONDS` should exceed the largest expected conversion.

## Graceful shutdown

The worker listens for SIGTERM and requests RQ stop. The API relies on Uvicorn's SIGTERM handling. In-flight inline jobs are not used in production.

## Backups

- PostgreSQL: enable Render point-in-time recovery / daily backups.
- Object storage: enable bucket versioning.
- Redis is expendable; jobs remaining `queued` in Postgres can be re-enqueued.

## Retention

Run periodically (cron or worker heartbeat):

```python
from docuflow.jobs.retention import cleanup_abandoned_jobs, cleanup_expired_files
```

Abandoned `processing` jobs older than 45 minutes are marked failed.

## Incidents

1. Check `/ready`.
2. Inspect failed jobs in the admin dashboard (`/admin`).
3. Confirm Redis and the worker process.
4. Confirm S3 credentials without printing them.
5. Refund or retry from admin only with a ledger reason.

## Dependency checks

```bash
uv run pip-audit || true
pnpm --filter web audit || true
```

`pip-audit` is not bundled by default; install it in CI when you enable scheduled scans.
