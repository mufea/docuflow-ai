# Render.com deployment

This application is designed for Render, not a single serverless function. The
**default cost-efficient stack** is:

1. Next.js web service (Free)
2. FastAPI web service (Free) with `JOB_BROKER=inline`
3. PostgreSQL (Free)
4. Render Cron for cleanup (billed only while running)
5. External S3-compatible bucket (Cloudflare R2, AWS S3, or MinIO)
6. Optional Free Redis / Key Value (unused while jobs are inline; kept for a
   future RQ worker)

A paid background worker is **not** in `infra/render.yaml`. Jobs run inside the
API process. Redis is not required for that mode. To add a queue later, see
`infra/render.scaling.yaml` — that path needs Redis and a paid worker.

The Blueprint is `infra/render.yaml` (not the repo root). Do not treat a
Blueprint sync as a completed production deploy. This repository is **NOT
DEPLOYED**.

## Required vs optional services

| Service | Required for current default? | Notes |
| --- | --- | --- |
| `docuflow-web` | Yes | Next.js UI |
| `docuflow-api` | Yes | FastAPI; runs jobs when `JOB_BROKER=inline` |
| `docuflow-db` | Yes | PostgreSQL is the source of truth |
| Object storage (R2/S3) | Yes in production | Render disks are ephemeral |
| `docuflow-cleanup` cron | Yes for retention | Billed only while the job runs; disable the API in-process loop (`CLEANUP_INTERVAL_SECONDS=0`) |
| `docuflow-redis` | Optional | Unused while jobs are inline; kept for a future RQ worker |
| `docuflow-worker` | Optional / not in default Blueprint | Paid. Use only with `JOB_BROKER=rq` |

Inline processing limits: one Free API instance, jobs share the web request CPU/memory budget, spin-down kills in-flight inline work, large PDFs can time out. A dedicated worker is justified when job runtime regularly exceeds the Free web budget, when you need isolation from HTTP, or when you want more than one consumer.

Provider limits change. Confirm the following against the current Render account
and [Render Free documentation](https://render.com/docs/free) before relying on
them. Values below were checked against that page on 5 Nov 2026 (Asia/Jakarta)
and are **not** a billing quote:

- Free web services spin down after 15 minutes idle and take about a minute to
  wake. They have an ephemeral filesystem, 750 Free instance hours per workspace
  per month, and cannot receive private-network traffic.
- Free Postgres: 1 GB, 100 connections, one active database per workspace,
  **no backups**, **no managed pooling**, expires 30 days after creation
  (14-day grace before deletion).
- Free Key Value: one per workspace, in-memory only, data lost on restart.
- Background workers are not a Free service type. A dedicated worker is paid
  (`infra/render.scaling.yaml` uses `0.5c-512mb`).
- Free web services cannot send outbound traffic on SMTP ports 25/465/587.

## Verification layers

| Layer | What it means | Status |
| --- | --- | --- |
| Local development | SQLite or local Postgres, filesystem storage, `JOB_BROKER=inline` | Supported. See `README.md` |
| Local verification | pytest / ruff / mypy / web lint-typecheck-test-build | See `docs/IMPLEMENTATION_STATUS.md` |
| CI verification | GitHub Actions (`postgres:16` for integration tests) | Phase 9.6 merge is `d65f087` (PR #9). Phase 9.7 branch CI succeeded on `2cbecde` ([run 42046952750](https://github.com/mufea/docuflow-ai/actions/runs/42046952750), 5 Nov 2026, 21:38 Asia/Jakarta) |
| Provider verification | Dedicated test bucket + `TEST_S3_*` credentials | **Pending** — mocked S3 tests are not provider verification |
| Staging deployment | Isolated non-production Render workspace + staging DB + staging bucket | **Not performed / not verified** |
| Production deployment | Live Render workspace serving users | **NOT DEPLOYED — Awaiting owner approval** |

## Local vs staging vs production

| | Local development | Staging (template only) | Production |
| --- | --- | --- | --- |
| Purpose | Engineer laptop / CI | Owner-approved isolated preview | Live users |
| Blueprint | none | `infra/render.staging.yaml` | `infra/render.yaml` |
| `DOCUFLOW_ENV` | `development` or `test` | `production` (fail-fast still applies) | `production` |
| Database | SQLite or local Postgres | Dedicated `docuflow-staging-db` | Dedicated `docuflow-db` |
| Object storage | filesystem | Dedicated staging bucket | Dedicated production bucket |
| Job broker | `inline` | `inline` | `inline` (default) |
| Exists today? | Yes | **No evidence in this repository** | **NOT DEPLOYED** |

Do not treat a Git merge or GitHub Actions success as staging or production.

## Staging verification workflow

This workflow is for an owner. It has **not** been executed from this environment.

1. Review `infra/render.staging.yaml` and `docs/staging.env.example`.
2. Use a **separate** Render workspace. Do not sync the staging Blueprint into a workspace that already has `docuflow-api`.
3. Create a dedicated S3-compatible **staging** bucket. Do not reuse the production bucket.
4. Fill `S3_*` and confirm `DOCUFLOW_SECRET_KEY` is unique and at least 32 characters.
5. Apply the staging Blueprint only after owner approval. This phase does not apply it.
6. Run the staging migration checklist below against that staging database only.
7. Hit staging `/health` (HTTP 200) and `/ready` (HTTP 200, or HTTP 503 if a required dependency is down).
8. Optionally: `STAGING_API_URL=https://… python scripts/staging_smoke.py`
9. Optionally: `uv run pytest -q -m provider` with dedicated `TEST_S3_*` (not production).

Until those steps run against a real staging workspace, staging remains **not verified**.

## First deploy on Render

Do this from a GitHub (or GitLab) repo that already has this code, including
`infra/render.yaml`. Render builds from that remote, not from your laptop.

1. Push `main` to the GitHub repo you will connect.
2. Sign in at [dashboard.render.com](https://dashboard.render.com).
3. **New → Blueprint**. Connect the GitHub repo if prompted.
4. Set the Blueprint file to `infra/render.yaml`. Render’s default is
   `render.yaml` at the repo root; that path is wrong for this project.
5. Confirm the plan column: `docuflow-web`, `docuflow-api`, `docuflow-db`,
   and `docuflow-redis` should be **Free**. There is no `docuflow-worker` in
   the default Blueprint. Do not add a paid worker unless you switch the API
   to `JOB_BROKER=rq` using `infra/render.scaling.yaml`.
6. Fill the Blueprint fields marked `sync: false` on `docuflow-api` before
   you apply:

   | Key | What to put |
   | --- | --- |
   | `S3_BUCKET` | Bucket name |
   | `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Bucket credentials |
   | `S3_ENDPOINT_URL` | e.g. `https://<account>.r2.cloudflarestorage.com` |
   | `DOCUFLOW_PUBLIC_WEB_URL` | `https://docuflow-web.onrender.com` (update after first deploy if the hostname differs) |
   | `DOCUFLOW_PUBLIC_API_URL` | `https://docuflow-api.onrender.com` |
   | `DOCUFLOW_CORS_ORIGINS` | Same origin as the web URL, no trailing slash |
   | `DOCUFLOW_TRUSTED_HOSTS` | Web and API hostnames, comma-separated, no `https://` |

   Leave `DATABASE_URL` alone — Render injects it. `REDIS_URL` is injected if
   Redis exists; the API ignores it while `JOB_BROKER=inline`.
   Leave the `postgres://` URL as-is; the API rewrites it to psycopg3.

7. Apply the Blueprint. Render creates Postgres (and Redis if listed), then
   builds API, web, and the cleanup cron. The first Free web build can take
   several minutes; the first HTTP request after idle takes about a minute
   while the service wakes up. No paid worker is created.
8. After both web services have public URLs, set
   `DOCUFLOW_PUBLIC_WEB_URL`, `DOCUFLOW_PUBLIC_API_URL`,
   `DOCUFLOW_CORS_ORIGINS`, and `DOCUFLOW_TRUSTED_HOSTS` to the real
   `*.onrender.com` hosts, then redeploy the API (and web if you changed
   anything it reads).
9. Open the **web** URL, not the API URL. Health checks:
   `https://<api-host>/health` and `https://<api-host>/ready`.

### Login or signup returns HTML, truncated JSON, or “incomplete response”

The browser asked for JSON and got something else. Typical Render causes:

1. **`API_INTERNAL_URL` is missing on the web service**, so `/v1` is proxied to
   `localhost` and Next.js returns its HTML error page. Set
   `API_INTERNAL_URL` (and optionally `DOCUFLOW_PUBLIC_API_URL`) to the API’s
   public URL, for example `https://docuflow-api.onrender.com`. Use `https://`,
   not Render’s private `http://<service>:10000` host — Free web services
   cannot receive private-network traffic.
2. **`API_INTERNAL_URL` points at the web service or custom domain.** The web
   proxy then calls itself. It must be the **API** public `https://…onrender.com`
   URL, not the marketing site.
3. **The API is asleep.** Free web services spin down after 15 minutes. Open
   `https://<api-host>/health` once, wait about a minute, then sign in again.
4. **`DOCUFLOW_TRUSTED_HOSTS` is still localhost or omits your custom domain.**
   Starlette used to answer `Invalid host header` as plain text, which the
   signup form showed as an “incomplete response.” Set
   `DOCUFLOW_TRUSTED_HOSTS` to `.onrender.com` plus the custom hostname, set
   `DOCUFLOW_PUBLIC_WEB_URL` / `DOCUFLOW_CORS_ORIGINS` to the real site URL,
   and redeploy the API.

### Tools return `Invalid request origin`

Upload and job POSTs check the browser `Origin` against
`DOCUFLOW_CORS_ORIGINS`. A custom domain that is not in that list used to fail
CSRF even when you were signed in. The web proxy now sends the site Host, and
the API accepts that origin plus `*.onrender.com` in production. Still set
`DOCUFLOW_PUBLIC_WEB_URL` and `DOCUFLOW_CORS_ORIGINS` to the URL you open in
the browser (custom domain or `https://<web>.onrender.com`), then redeploy the
API and web.

### Jobs stay `queued` (Word to PDF never starts)

The Blueprint used to set `JOB_BROKER=rq` on the API. Redis then holds the job
until `docuflow-worker` picks it up. Render workers are paid, so a Free stack
often has **no worker** and the job never leaves `queued`.

The API now runs the job itself. On the live `docuflow-api` service, keep
`JOB_BROKER=inline` (the Blueprint default). You do not need a paid worker for
Word to PDF.

### Fully Free (no worker bill)

The default Blueprint does not create `docuflow-worker`. Keep
`JOB_BROKER=inline` on `docuflow-api`. PDF jobs run inside the API process.
That is slower and can time out on large files. No dollar savings are claimed
here beyond avoiding a paid worker that the current inline path does not use.

If an older Blueprint already created `docuflow-worker`, stop or delete it in
the dashboard only after confirming `JOB_BROKER=inline` and that no RQ
consumers remain. This agent does not delete live services.

### Already created the services?

Sync the existing Blueprint, or change each service’s instance type in
**Settings**. See the next section. Do not create a second Free Postgres or
Free Key Value in the same workspace — Render allows only one of each.

## Changing existing Render services to Free

Editing this repo does not move live services by itself. After you pull and
push to the repo Render deploys from:

1. In the Render dashboard, open the Blueprint (or **New → Blueprint** and
   point it at `infra/render.yaml`), then sync / apply.
2. If a service is still on Starter or Basic after the sync, open it →
   **Settings** (or **Info** for datastores) → **Instance type** / **Plan** →
   **Free** → save.
3. Do this for `docuflow-web`, `docuflow-api`, `docuflow-db`, and
   `docuflow-redis`. If `docuflow-worker` already exists, leave it stopped or
   delete it only with owner approval after switching the API to inline.
4. Confirm Billing shows $0 for the Free resources. A payment method is not
   required for this default stack unless you add a worker or leave one
   running from an older Blueprint.

Render keeps the current plan when a Blueprint omits `plan`. This file now
sets `plan` explicitly. A Blueprint apply still will not recreate a datastore
just to change its plan; use the dashboard if Postgres or Redis stay paid.

Do not treat the Blueprint as a completed production deploy.

## Build and start

- Web: `corepack pnpm install --frozen-lockfile && corepack pnpm --filter web build`
  then `corepack pnpm --filter web start -p $PORT`. Do not run `corepack enable`
  on Render — it tries to write `/usr/bin/pnpm` and fails with EROFS.
- API: `pip install -r requirements.txt` then
  `python -m docuflow.migrate && uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT`
- Worker: not started in the default stack. `python -m docuflow.worker` requires `JOB_BROKER=rq`.
- Cleanup cron: `python -m docuflow.migrate && python -m docuflow.cleanup` every 15 minutes.
  Render bills the cron only while it runs. The API in-process cleanup
  thread is disabled (`CLEANUP_INTERVAL_SECONDS=0`) so cron is the single
  scheduler. Skip creating the cron only if you accept cleanup only while the
  API process is awake, and then set `CLEANUP_INTERVAL_SECONDS=900` on the API.
- Migrations: Render Free rejects `preDeployCommand`, so the API start command
  runs `python -m docuflow.migrate` (Alembic upgrade under a Postgres advisory
  lock) and then uvicorn. Alembic itself is idempotent. The lock is for a
  later multi-replica API. Do not run migrate on a worker. The cleanup cron
  also runs migrate so revision `0003_cost_efficient_reliability` exists
  before the first sweep. Do not run production migrations from this environment.

## Required production environment

See `.env.example`. At minimum:

- `DOCUFLOW_ENV=production`
- `DOCUFLOW_SECRET_KEY` (unique, at least 32 characters)
- `DATABASE_URL` (Render Postgres). Leave the injected `postgres://` value as-is.
  The API and Alembic rewrite it to `postgresql+psycopg://` so SQLAlchemy uses
  psycopg3. Do not install `psycopg2`.
- `STORAGE_BACKEND=s3` plus bucket credentials (Render disk is ephemeral)
- `COOKIE_SECURE=true` (forced on when `DOCUFLOW_ENV=production`)
- `DOCUFLOW_PUBLIC_WEB_URL` / `DOCUFLOW_PUBLIC_API_URL`
- `DOCUFLOW_CORS_ORIGINS` and `DOCUFLOW_TRUSTED_HOSTS`
- `API_INTERNAL_URL` on the **web** service = API public `https://…onrender.com` URL

Job broker (choose one mode; do not mix):

| Mode | API `JOB_BROKER` | Worker | Redis |
| --- | --- | --- | --- |
| Minimal cost (default) | `inline` | Not in the Blueprint | Optional. Unused. Blueprint still lists Free Key Value for compatibility |
| Worker deployment | `rq` on API | Paid worker from `infra/render.scaling.yaml` | Required. Same `REDIS_URL` and `RQ_QUEUE_NAME=docuflow` |

Also used by cleanup: `CLEANUP_LEASE_MINUTES` (default 5) and
`STORAGE_DELETE_LEASE_MINUTES` (default 5). S3 HTTP connect+read time for the
SDK call (`total_max_attempts=2`) is kept at or below half the deletion lease.
Botocore standard backoff (about 20s per retry, with jitter) is extra and not a
hard deadline. Alembic revision
`0003_cost_efficient_reliability` adds lease timestamps on `cleanup_leases`
and reclaim fields on `storage_deletions`. Do not run that migration against
production from this environment. See the staging procedure below.

Keep `OCR_ENABLED=true`. Native Render Python images do not include Tesseract;
OCR uses the bundled RapidOCR ONNX engine in that case. Tesseract is used when
it is present on PATH.

Optional: SMTP, Stripe, Midtrans, `AI_API_KEY`. Defaults stay mock/console until
those are intentionally enabled. See **AI and email readiness** below.

## Staging migration (Alembic `0003`)

Do this only against a **staging** database. Do not run it against production
from this environment. Do not delete or recreate the production database.
This checklist has **not** been executed against a hosted staging database
from this environment.

1. **Database backup.** Print the destination DSN host and database name (not
   the password). Abort if the host is production. Take a `pg_dump` first.
   Free Render Postgres has **no managed backups**. Store the dump outside
   the target instance. See **Database backup and recovery** below.
2. **Database connectivity.** `DATABASE_URL=... uv run alembic current` must
   connect. Expected before `0003`: `0002_runtime_reliability`. If `0003` is
   already current, stop — do not re-run blindly.
3. **Migration execution.** `DATABASE_URL=... python -m docuflow.migrate`
   On PostgreSQL this takes advisory lock `86420138` so two boots do not race.
4. **Schema verification.** Confirm `cleanup_leases.acquired_at` /
   `updated_at` and `storage_deletions.started_at` / `lease_until` /
   `owner_token` exist, all nullable. Confirm index
   `ix_storage_deletions_lease_until`. `alembic current` should report
   `0003_cost_efficient_reliability` and match `alembic heads`. Existing
   `storage_deletions.storage_key` rows must still be present.
5. **Application smoke test.** Hit staging `/health` (HTTP 200) and `/ready`
   (HTTP 200 if dependencies are up, HTTP 503 if a required dependency is
   down). Neither payload should include credentials, DSNs, signed URLs, or
   stack traces. Then follow **Staging smoke-test checklist** below.
   Integration tests belong on a throwaway database, never on production and
   not on the staging primary if it holds real staging documents.
6. **Backup restoration procedure.** `alembic downgrade 0002` drops those
   columns and the lease index. In-flight leases and deletion owner tokens
   are lost. Pre-existing outbox `storage_key` values remain. Restore from
   the dump if the downgrade is not enough. There is no automatic Render
   rollback of Postgres on Free. Do not invent a lossless in-place rollback.

Local automated coverage for upgrade/downgrade exists in
`tests/integration/test_migrations.py` (isolated Postgres). That is **not**
staging verification.

Production migration status: **not applied and not verified.**
Staging migration status: **not executed / not verified.**

## Owner-operated S3 provider verification

Mocked S3 tests are **not** provider verification.

Use a dedicated test bucket and keys. Never production.

```bash
export TEST_S3_BUCKET=...
export TEST_S3_ACCESS_KEY_ID=...
export TEST_S3_SECRET_ACCESS_KEY=...
# optional
export TEST_S3_ENDPOINT_URL=...
export TEST_S3_REGION=auto
uv run pytest -q -m provider
```

The test writes only `docuflow-test/<uuid>/probe.bin` and deletes that key.
It skips when credentials are missing so CI stays green. Do not log the
values. The application has no global key prefix, so a **dedicated bucket**
is required for staging/production isolation — a prefix on a shared
production bucket is not enough.

This procedure has **not** been executed from this environment.

## Staging smoke-test checklist

**NOT EXECUTED** against a staging environment (no `STAGING_API_URL`).

Automated liveness/readiness only:

```bash
# Exits 2 with NOT EXECUTED when unset — safe for CI.
python scripts/staging_smoke.py
STAGING_API_URL=https://docuflow-staging-api.onrender.com python scripts/staging_smoke.py
```

Owner manual checks after a real staging API exists:

| Step | What to confirm | Status here |
| --- | --- | --- |
| 1. API startup | Process stays up; fail-fast does not abort | NOT EXECUTED |
| 2. `GET /health` | HTTP 200, `status=ok` | NOT EXECUTED |
| 3. `GET /ready` | HTTP 200 if DB+storage up; HTTP 503 if not | NOT EXECUTED |
| 4. PostgreSQL | `/ready` checks.database true | NOT EXECUTED |
| 5. Migration | `alembic current` is `0003_cost_efficient_reliability` | NOT EXECUTED |
| 6. Authentication | register/login on staging, CSRF cookie set | NOT EXECUTED |
| 7. Document upload | PDF upload 200 for the staging user | NOT EXECUTED |
| 8. Document processing | `extract_text` (or similar) job completes | NOT EXECUTED |
| 9. File download | Owner can download; other user gets 403 | NOT EXECUTED |
| 10. Background jobs | `JOB_BROKER=inline`; job leaves `queued` | NOT EXECUTED |
| 11. Credit ledger | reserve then settle or refund once | NOT EXECUTED |
| 12. Error handling | `/ready` 503 body has no DSN/signature | NOT EXECUTED |
| 13. Worker/API | No paid worker in default staging stack | N/A (inline) |
| 14. S3 integration | Upload visible in the **staging** bucket only | NOT EXECUTED |

## AI and email readiness

Blueprint and application defaults:

| Setting | Current default | Production-ready? |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | No. Deterministic local summaries/Q&A only. Live calls need `openai_compatible`, `AI_API_KEY`, and a base URL/model you control. |
| `EMAIL_BACKEND` | `console` | No. Prints to logs. SMTP needs `EMAIL_BACKEND=smtp`, `SMTP_HOST`, and credentials. Render Free web services block outbound 25/465/587; verify current network policy before enabling SMTP on Free. |

Do not put AI or SMTP secrets in the Next.js bundle. This phase does not switch
mock providers to live providers and does not add keys.

## Two Render modes

### A. Minimal cost (default Blueprint)

- `docuflow-web` Free, `docuflow-api` Free, `docuflow-db` Free, optional Free Redis
- No `docuflow-worker`
- `JOB_BROKER=inline` on the API
- One cleanup cron every 15 minutes; API `CLEANUP_INTERVAL_SECONDS=0`
- Jobs run in the API process. Slower, and a Free instance can time out or die on spin-down
- No verified dollar amount is claimed here; this is the stack that avoids a paid worker

### B. Worker deployment (not applied by default)

- Same web, API, Postgres, and Redis
- Paid `docuflow-worker` from `infra/render.scaling.yaml` (`0.5c-512mb` because Render has no Free worker)
- `JOB_BROKER=rq` on **both** API and worker
- Same S3 bucket and `DOCUFLOW_SECRET_KEY` on API and worker
- Better isolation for heavy PDFs; Redis restart still does not lose durable job rows

Do not set the API to `rq` unless the worker is actually running. The API will
fall back to inline when no RQ worker heartbeat is visible, but a live service
that still has `JOB_BROKER=rq` from an older Blueprint should be changed to
`inline` in the dashboard if you skipped the worker.

## Status

| Checkpoint | Status |
| --- | --- |
| Local development | Supported |
| Automated tests | See `docs/IMPLEMENTATION_STATUS.md` |
| Render configuration | Blueprint present; validate in the Render dashboard |
| Successful Render deployment | **NOT DEPLOYED** — not verified from this environment |
| Staging Blueprint | Template `infra/render.staging.yaml` — **not applied** |
| Staging migration `0003` | **Not performed** |
| Production migration `0003` | **Not performed** |
| Live provider verification | **Not performed** — requires authorization |

## Health

- `/health` — liveness only. HTTP 200 if the API process is up. Render
  `healthCheckPath` stays `/health` so a dependency outage does not mark the
  Free web service as fully dead.
- `/ready` — HTTP 200 when required dependencies can accept traffic; HTTP 503
  with `status=degraded` when database, object storage, or Redis (only if
  `JOB_BROKER=rq`) fails. Zero RQ workers is informational and does not fail
  readiness. The JSON body does not echo secrets, DSNs, signed URLs, or
  stack traces.

## Database backup and recovery

This section is a runbook. It was **not** executed against staging or
production from this environment. The Blueprint lists a Free Postgres
instance; the **live** Render plan must be read from the dashboard. Do not
assume they match.

### Persistence risk

| Kind | What it is | Typical Render Free Postgres | Paid Render Postgres (confirm plan) |
| --- | --- | --- | --- |
| Backup | A point-in-time file you can restore (for example `pg_dump`) | **Not provided.** You must take your own dumps. | Often daily backups; confirm in the dashboard |
| Snapshot | A disk/image copy of the instance | Not a documented Free feature | May exist on paid instance types |
| Point-in-time recovery (PITR) | Restore to a timestamp using WAL | **Not available on Free** | Paid plans may offer it; confirm before relying on it |

Free Postgres also has no managed pooling, a 30-day expiry after creation, and
a 14-day grace period. Losing the instance without a dump is permanent data
loss.

### Recommended production backup (lowest extra cost)

1. Confirm the dashboard plan. If it is Free, do not wait for Render backups.
2. Take a logical dump on a schedule you control (`pg_dump`). Store it
   **outside** the database instance (another machine, object storage you
   already pay for, or encrypted local disk).
3. Keep at least three successful dumps (for example daily, with 7-day
   retention) unless a paid PITR plan is confirmed.
4. Do **not** add a Render cron whose only job is backup unless the owner
   accepts the extra runtime cost. A laptop or existing jump host is enough.
5. Redis/Key Value is expendable. Do not back it up. Job rows live in
   Postgres.
6. Object storage (R2/S3) is a separate recovery domain. Enable versioning on
   the **test or production bucket you actually use**, if the provider offers
   it. That is not a Postgres backup.

### `pg_dump` (logical backup)

Use a role that can read application tables. Do not put the password on the
command line or in this repository. Prefer `.pgpass` or `PGPASSWORD` in an
operator shell that is not logged.

Print only host and database name before you run anything. Abort if the host
is production and you do not have owner approval.

```bash
# Replace HOST and DB only. Do not paste passwords into tickets or docs.
pg_dump --format=custom --no-owner --no-acl \
  --host HOST --port 5432 --username USER --dbname DB \
  --file docuflow-$(date -u +%Y%m%dT%H%M%SZ).dump
```

`--format=custom` is the `pg_restore` format. A directory of SQL is fine for
tiny databases (`pg_dump --format=plain`), but custom format restores more
selectively.

### Verify a dump

```bash
pg_restore --list docuflow-YYYYMMDDThhmmssZ.dump | head
# Confirm expected tables such as users, jobs, documents, credit_ledger,
# cleanup_leases, storage_deletions. The dump file size should be non-zero.
```

Keep the listing output; it is the cheapest proof the file is not empty.

### Restore (disposable target only)

Restore onto an **empty** database you are allowed to destroy. Never restore
onto the live production database from this environment.

```bash
# Create an empty database first. Then:
pg_restore --no-owner --no-acl --dbname DB --host HOST --port 5432 --username USER \
  docuflow-YYYYMMDDThhmmssZ.dump
```

If you used `--format=plain`, pipe the SQL file through `psql` instead of
`pg_restore`. After restore, run `uv run alembic current` against that
database and compare to `alembic heads`. Hit `/health` and `/ready` only on a
staging API pointed at that restored database.

### Recovery checklist

1. Identify the incident (data corruption, dropped table, lost Render
   instance, bad migration).
2. Stop writers if the source database is still reachable (scale the API to
   zero or disable the Blueprint services). Owner approval required.
3. Choose the newest dump that predates the incident.
4. Restore onto a new database, not over the only remaining copy.
5. Verify row counts for `users`, `jobs`, and `credit_ledger` against
   expectations you recorded when the dump was taken.
6. Point a **staging** API at the restored database and check `/health` plus
   `/ready`.
7. Production cutover requires owner approval.

### Data-loss and downtime

| Failure | Without a dump | With a recent dump |
| --- | --- | --- |
| Free instance expired or deleted | Permanent loss | Restore time + DNS/config cutover |
| Accidental `DROP` / bad migration | Permanent unless PITR exists | Restore to a new database; downtime while you cut over |
| Render regional outage | Service down; data may return | Dump is a second copy, not high availability |

Expect downtime measured by dump size and how long it takes to re-point the
API. This runbook is not a high-availability design.

### Retention (cost-efficient)

Keep the last 7 daily dumps plus one dump from before each migration. Delete
older files. Encrypted object storage you already use is cheaper than a new
backup product. Do not add a paid backup add-on from this phase.

## Object storage

Do not store uploads on the Render disk. Configure R2 or S3 before enabling public sign-ups.

## Rollback

Render keeps previous deploys. Roll back the web, API, and worker together if the API schema changed. Database downgrades are not automatic; restore from a Postgres backup if a migration must be undone.

## HTTPS and domains

Terminate TLS at Render. Point the custom domain at the web service and set `DOCUFLOW_PUBLIC_WEB_URL` accordingly. The web service proxies `/v1` to the API so cookies stay first-party.
