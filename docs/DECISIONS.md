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

Web, API, Postgres, and Key Value use `plan: free` in `infra/render.yaml` so a
hobby workspace is not billed for those four. Render does not sell a Free
background worker, so the worker remains on `0.5c-512mb`. Free web spin-down,
30-day Postgres expiry, and in-memory Redis are accepted for this hobby slice;
they are not production SLAs.

## Hatchling / uv for Python, pnpm for the web

Lockfiles: `uv.lock` and `pnpm-lock.yaml`.
