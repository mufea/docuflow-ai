# Decisions

## RQ instead of Celery

RQ maps cleanly onto Render Redis, has a small operational surface, and jobs are identified by our Postgres `job_id`. Celery remains an option if we later need multi-broker routing; switching is isolated behind `JobBroker`.

## SQLAlchemy + Alembic

Required by the product spec and appropriate for PostgreSQL. Tests may use SQLite with the same models. Production race-safety for credits uses `SELECT ... FOR UPDATE`, which is fully meaningful on PostgreSQL.

## Inline broker for development

Redis is not assumed on a developer laptop. The inline broker still writes job rows and uses the same `JobRunner` as RQ.

## Mock AI default

Keeps the PDF product usable without paid APIs and prevents accidental spend in tests.

## No live billing

Checkout returns `not_activated` until secrets are configured and an operator explicitly enables charges. Webhooks are implemented and tested with fixtures.

## Render Free compute where Render allows it

Web, API, Postgres, and Key Value use `plan: free` in `infra/render.yaml`.
Phase 9.2 keeps `JOB_BROKER=inline` and omits the paid background worker from
the default Blueprint because the API does not enqueue to RQ in that mode.
Redis stays listed for compatibility and as the future RQ transport; it is
unused while jobs are inline. A paid worker remains a documented scaling
option in `infra/render.scaling.yaml`. Free web spin-down, 30-day Postgres
expiry, and in-memory Redis are accepted for this hobby slice; they are not
production SLAs.

## Built-in OCR on hosts without Tesseract

Render native Python images do not ship the `tesseract` binary. OCR stays
on with `OCR_ENABLED=true` and uses RapidOCR ONNX (`rapidocr` + `onnxruntime`)
when Tesseract is missing. Tesseract is still preferred when it is on PATH.

## Seed never changes user entitlements

`seed_reference_data()` runs on API startup. It may insert missing plans and
operation costs, update catalog display fields, and raise (never lower) plan
limits. It must not write `User`, `CreditAccount`, or `CreditLedger` rows.
Plan changes for an account go through billing webhooks or an explicit admin
grant.

## Scheduled cleanup, not request-path cleanup

Abandoned jobs and expired files are processed by `python -m docuflow.cleanup`.
The default Render Cron is the single production scheduler. The API
in-process interval is disabled there (`CLEANUP_INTERVAL_SECONDS=0`). Cleanup
coordination uses a database lease on `cleanup_leases`, not session-level
Postgres advisory locks (unsafe with connection pooling). Storage deletes go
through an outbox whose `in_progress` rows expire and can be reclaimed after a
crash so a failed S3 call cannot resurrect a document the user already lost.

## Botocore `total_max_attempts` instead of `max_attempts`

On botocore 1.43, a client Config `retries.max_attempts` value means extra
*retries*, not total tries (`total = retries + 1`). Phase 9.3 passed
`max_attempts=2` while budgeting two HTTP attempts, so the SDK could issue
three. Phase 9.4 sets `total_max_attempts=2` (one retry) and keeps
application outbox retries on `storage_deletions` as a separate bounded loop.

## Bounded storage timeouts instead of a threaded lease heartbeat

The deletion lease is renewed before the object-storage call. A hung S3 request
with no client timeout could outlive `STORAGE_DELETE_LEASE_MINUTES`. A
background heartbeat would need a second SQLAlchemy session (sessions are not
thread-safe) and an always-running helper thread. Phase 9.3 bounds boto3
connect/read timeouts so the retry budget stays under half the lease, maps
timeouts to `TransientError`, and heartbeats the *cleanup* lease between
items. Overlapping deletes are not claimed to be impossible.

## Hatchling / uv for Python, pnpm for the web

Lockfiles: `uv.lock` and `pnpm-lock.yaml`.
