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

The worker listens for SIGTERM and requests RQ stop. The API relies on Uvicorn SIGTERM handling. In-flight inline jobs on a Free API die when the instance spins down; remaining `queued` rows stay in Postgres. The API re-enqueues up to 100 `queued` jobs at process start and again on the next job GET. `processing` jobs are not reset; cleanup fails them after `JOB_STALE_MINUTES` and refunds once.

## Health

- `GET /health` — liveness only (HTTP 200 if the process is up). Render should use this path.
- `GET /ready` — HTTP 200 when required dependencies can accept traffic; HTTP 503 when database, storage, or Redis (only if `JOB_BROKER=rq`) fails. Storage is never reported true without a check. `rq_workers` is informational and does not fail readiness. The JSON body does not echo secrets.

## Backups

See **Database backup and recovery** in `docs/DEPLOYMENT.md`. Production
restore and isolated drill: `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`.
Do not assume the live Render Postgres plan matches the Blueprint. Free
Postgres has no managed backups. Object-storage versioning is a separate
control on the bucket you actually use. Redis is expendable.

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
- Overlapping runs take a PostgreSQL-backed `cleanup_leases` row (`name`, owner `token`, `locked_until` / `lease_until`, `acquired_at`, `updated_at`). Acquisition is an atomic `UPDATE` of an expired or unowned row. Session-level advisory locks are not used; they are unsafe with connection pooling. The owner renews the lease between cleanup stages, between expired-document rows, and between storage-deletion items. A process that loses ownership stops remaining work. Only the current owner token can renew or release. After a crash the lease expires and another process can reclaim it. There is no heartbeat *during* a single blocking storage call (SQLAlchemy sessions are not shared across threads).
- A job is abandoned only when `status=processing` and `heartbeat_at` (or `started_at` if no heartbeat) is older than `JOB_STALE_MINUTES`, which is never below the worker timeout plus grace. Fail + refund is one transaction.
- Expired uploads/results (`FILE_RETENTION_HOURS` / `RESULT_RETENTION_HOURS`) are marked deleted, then object storage is removed through `storage_deletions`. Rows left `in_progress` past `STORAGE_DELETE_LEASE_MINUTES` are reclaimed. Completion and failure updates require the claiming owner token, so an expired worker cannot overwrite a newer owner.
- S3-compatible calls use Botocore `total_max_attempts=2` (one initial request and at most one retry). That is **not** `max_attempts`, which Botocore treats as extra retries and would add a third try. Connect and read timeouts are sized so `attempts × (connect + read)` stays at or below half the deletion lease. Standard-mode backoff is documented at 20s per retry with jitter; it is **not** a hard SDK wall-clock deadline. Timeouts, 5xx, `SlowDown`, and throttling are `TransientError`. `NoSuchKey` / HTTP 404 on delete is idempotent success; `AccessDenied` and similar are not. Duplicate deletes remain possible if a provider ignores client timeouts. Completed rows are not processed again. Failed object deletes never undelete the row.
- Application-level `storage_deletions` retries (bounded by `STORAGE_DELETE_MAX_ATTEMPTS` and exponential minutes) are a separate outbox loop. They are not multiplied into the SDK call.

```
python -m docuflow.cleanup
```

## Incidents

Production scenarios (API down, database, storage, cleanup cron, suspected
data loss, credential exposure):
`docs/runbooks/PRODUCTION_INCIDENT_RESPONSE.md`.
Business continuity / DR **objectives** (RTO 4 h / RPO 24 h, owner-approved
targets; 9.19 capability **NOT DEMONSTRATED**):
`docs/runbooks/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md`.
Recovery readiness checklist:
`docs/runbooks/RECOVERY_READINESS_CHECKLIST.md`.
Capability assessment: `docs/reports/PHASE_9_19_RECOVERY_CAPABILITY_GAP_ASSESSMENT.md`.
Database restore: `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`.

1. Check `/health` then `/ready`. HTTP 503 with `status=degraded` names the failed dependency without secrets.
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
