# Render.com deployment

This application is designed for Render, not a single serverless function. The
**default cost-efficient stack** is:

1. Next.js web service (Free)
2. FastAPI web service (Free) with `JOB_BROKER=inline`
3. PostgreSQL — git Blueprint `docuflow-db` `plan: 0.1c-256mb` (Basic).
   Live production is owner-reported Basic with backups enabled (retention,
   frequency, PITR, last backup: **NOT VERIFIED**). Staging Postgres remains
   Free in `infra/render.staging.yaml`.
4. Render Cron for cleanup (billed only while running)
5. External S3-compatible bucket (Cloudflare R2, AWS S3, or MinIO)
6. Optional Free Redis / Key Value on the **production Blueprint** (unused
   while jobs are inline). Live production has **no** Redis. Staging omits Redis.

A paid background worker is **not** in `infra/render.yaml`. Jobs run inside the
API process. Redis is not required for that mode. To add a queue later, see
`infra/render.scaling.yaml` — that path needs Redis and a paid worker.

The Blueprint is `infra/render.yaml` (not the repo root). Do not treat a
Blueprint sync as a completed production deploy by itself.

**Current production (Phase 9.12, 7 Nov 2026):** deployed and owner-verified
for the mandatory functional/isolation smoke. API
`https://docuflowai.site`. CMS `https://docuflowai.online`.
`JOB_BROKER=inline`. No Redis, no worker. Cleanup cron owner-reported
running. Isolated restore drill **VERIFIED** (9.13B) on
`docuflow-db-restore-drill-20261107` with Alembic
`0003_cost_efficient_reliability`. Production DSN was not opened; production
was not cut over.

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
| CI verification | GitHub Actions (`postgres:16` for integration tests) | Phase 9.9 merge is `ae3cc0b` (PR #12, [run 42167872331](https://github.com/mufea/docuflow-ai/actions/runs/42167872331), 6 Nov 2026, 12:22 Asia/Jakarta). Phase 9.10 branch CI on `7d9da7f` succeeded ([run 42172770416](https://github.com/mufea/docuflow-ai/actions/runs/42172770416), 6 Nov 2026, 13:12 Asia/Jakarta) |
| Provider verification | Dedicated test bucket + `TEST_S3_*` credentials | Owner-run `pytest -q -m provider`: 1 passed, 246 deselected (6 Nov 2026, 19:57 Asia/Jakarta). Mocked S3 tests are not this result |
| Staging deployment | Isolated non-production Render workspace + staging DB + staging bucket | **STAGING VERIFIED** (9.10D). Hosted Alembic `0003` PASS. Live cross-user 403/401 PASS. Not production. |
| Production deployment | Live Render workspace serving users | **PRODUCTION VERIFIED** (9.12 owner-run smoke). API `https://docuflowai.site`, CMS `https://docuflowai.online`. Isolated restore drill **VERIFIED** (9.13B). Production Alembic inferred from restore copy only. |

## Local vs staging vs production

| | Local development | Staging | Production |
| --- | --- | --- | --- |
| Purpose | Engineer laptop / CI | Owner-approved isolated preview | Live users |
| Blueprint | none | `infra/render.staging.yaml` | `infra/render.yaml` |
| `DOCUFLOW_ENV` | `development` or `test` | `production` (fail-fast still applies) | `production` |
| Database | SQLite or local Postgres | Dedicated `docuflow-staging-db` | Dedicated `docuflow-db` |
| Object storage | filesystem | Dedicated staging bucket | Dedicated production bucket |
| Redis | unused | **Omitted** from the staging Blueprint | Optional Free Key Value (unused while inline) |
| Job broker | `inline` | `inline` | `inline` (default) |
| Exists today? | Yes | **Yes** (owner-applied Blueprint; 9.10D verified) | **Yes** — API `https://docuflowai.site`, CMS `https://docuflowai.online` (9.12) |

Do not treat a Git merge or GitHub Actions success as staging or production.

## Staging verification workflow

This workflow is for an owner. It has **not** been executed from this environment.

1. Review `infra/render.staging.yaml` and `docs/staging.env.example`.
2. Use a **separate** Render workspace. Do not sync the staging Blueprint into a workspace that already has `docuflow-api`.
3. Create a dedicated S3-compatible **staging** bucket. Do not reuse the production bucket.
4. Fill `S3_*` and confirm `DOCUFLOW_SECRET_KEY` is unique and at least 32 characters.
5. Run `STAGING_PREFLIGHT=1 python scripts/staging_preflight.py` against the intended env. It refuses production database/bucket/host reuse and does not create resources.
6. Apply the staging Blueprint only after owner approval. This phase does not apply it.
7. Run the staging migration checklist below against that staging database only (`scripts/staging_migrate_verify.py`).
8. Hit staging `/health` (HTTP 200) and `/ready` (HTTP 200, or HTTP 503 if a required dependency is down).
9. Optionally: `STAGING_API_URL=https://… python scripts/staging_smoke.py`
10. Optionally: `uv run pytest -q -m provider` with dedicated `TEST_S3_*` (not production).

Until those steps run against a real staging workspace, staging remains **not verified**.

## Staging operator procedure

Owner-operated. This environment has **not** applied the Blueprint or
contacted a hosted staging database. Do not invent URLs, bucket names, or
credentials.

A valid Blueprint is **IMPLEMENTED**, not **PROVISIONED**. A local preflight
PASS is **LOCALLY TESTED**, not Render success.

### Evidence row

For every live check, record (never secrets, DSNs, or signed URLs):

| Field | Example |
| --- | --- |
| Date/time | Asia/Jakarta |
| Git commit SHA | `git rev-parse HEAD` of the deployed revision |
| Environment identity | staging API hostname, database **name** (not password), bucket **name** |
| Command | exact command |
| Result | PASS / FAIL / SKIPPED / NOT EXECUTED / BLOCKED |
| Layer | local / CI / provider / staging |

Statuses: **IMPLEMENTED**, **LOCALLY TESTED**, **CI VERIFIED**, **PROVISIONED**,
**STAGING VERIFIED**, **PRODUCTION VERIFIED**, **NOT EXECUTED**, **BLOCKED**.
Do not combine them. **PRODUCTION VERIFIED** (9.12) is not a restore drill.

A loopback smoke pass is **local**. GitHub Actions is **CI**. `pytest -m provider`
is **provider** only with dedicated `TEST_S3_*`. Render URLs are **staging**.

### Provisioning status (this repository)

| Component | Verification | Status |
| --- | --- | --- |
| Render workspace | Dedicated staging; no production service names | Owner-attested; services `docuflow-staging-*` live |
| PostgreSQL | `docuflow-staging-db` / `docuflow_staging_db` | **PROVISIONED** (Free, 30-day expiry). `/ready` database true |
| S3 / R2 | Staging bucket + provider-test bucket | Provider-test **owner-verified**; staging storage `/ready` true |
| API | `https://docuflow-staging-api.onrender.com` | **PROVISIONED** live; `/health` `/ready` **PASS** |
| Web | `https://docuflow-staging-web.onrender.com` | **PROVISIONED** live; HTTP 200 **PASS** |
| Cleanup | `docuflow-staging-cleanup` | Owner: live. Independent cron run **NOT EXECUTED** |
| Isolation | No Redis, no worker | Owner confirmed absent. Broker `inline` on `/ready` |
| Blueprint apply | `infra/render.staging.yaml` | **PROVISIONED** (owner-applied). Agent did not apply |

### Owner provisioning runbook

Do **not** execute Steps 7–12 from an agent.

1. Confirm the target Render workspace is dedicated staging. It must not contain
   `docuflow-api`, `docuflow-db`, or `docuflow-web`.
2. Confirm workspace plan and PostgreSQL availability. Render Free: one Postgres
   per workspace, 1 GB, **no managed backups**, **expires 30 days** after
   creation. If staging must outlive 30 days, stop and choose a paid Postgres
   plan before applying. Record the actual dashboard plan.
3. Prepare a dedicated S3-compatible bucket (owner-chosen provider: R2, AWS S3,
   or MinIO). Unique access key, unique secret, correct endpoint, region,
   upload/download/delete on that bucket only. Not a prefix in production.
4. Prepare staging environment variables from `docs/staging.env.example`. Never
   copy production `DATABASE_URL`, `S3_*`, `DOCUFLOW_SECRET_KEY`, Stripe,
   Midtrans, `AI_API_KEY`, or SMTP values.
5. Run staging preflight:

```bash
export STAGING_PREFLIGHT=1
# export the intended staging values, never production secrets
python scripts/staging_preflight.py
```

6. Review every preflight line. Stop on FAIL. Unset `STAGING_PREFLIGHT` is
   **NOT EXECUTED**.
7. Owner manually opens the dedicated Render workspace.
8. Select **New → Blueprint**. Connect the GitHub repo if prompted.
9. Set the Blueprint file to `infra/render.staging.yaml` (not
   `infra/render.yaml`).
10. Review resource names (`docuflow-staging-*`), Free plans, no Redis, no
    worker, `JOB_BROKER=inline`, and estimated costs (web hours, Postgres
    expiry, cron runtime, external storage). Staging is not zero-cost.
11. Require explicit owner approval before applying. Fill `S3_*` with the
    staging bucket only. Leave `DOCUFLOW_SECRET_KEY` on generateValue unless
    pasting a unique staging secret.
12. Record provisioning evidence (date/time Asia/Jakarta, git SHA, workspace
    identity, command/UI action, result). Do not record secrets.
13. Verify generated API and web URLs. They must not match `docuflow-api` /
    `docuflow-web`. Confirm env: `DOCUFLOW_ENV=production`,
    `JOB_BROKER=inline`, `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`,
    `STORAGE_BACKEND=s3`, `CLEANUP_INTERVAL_SECONDS=0`. `ipAllowList: []`
    keeps Postgres private; laptop migrate-verify needs an owner-added IP or a
    Render shell.
14. Run existing migration verification and staging smoke. Mutating smoke
    still needs `STAGING_SMOKE_MUTATIONS=1` and `STAGING_HOST_CONFIRM`.

```bash
export STAGING_MIGRATE_VERIFY=1
export DATABASE_URL=...              # staging only
export STAGING_DATABASE_CONFIRM=...  # database name or host/name
python scripts/staging_migrate_verify.py
# if pending and identity matched:
export STAGING_MIGRATE=1
python scripts/staging_migrate_verify.py

export STAGING_API_URL=https://<staging-api-host>
export STAGING_HOST_CONFIRM=<staging-api-hostname>
export STAGING_WEB_URL=https://<staging-web-host>
python scripts/staging_smoke.py
```

`GET /health` HTTP 200 alone is **not** staging verification.

### S3 bucket checklist

Owner confirms the provider. Do not assume Cloudflare R2 or AWS S3.

- Dedicated staging bucket name (not `docuflow-documents`, not production)
- Unique access key and secret (not production keys)
- Endpoint URL for R2/MinIO; AWS may use the default endpoint
- Region (`auto` in the Blueprint; change in the dashboard if the provider needs it)
- Permissions: PutObject, GetObject, DeleteObject, HeadBucket/HeadObject
- Prefix isolation inside the production bucket is **not** sufficient
- Optional live roundtrip: dedicated `TEST_S3_*` with `uv run pytest -q -m provider`

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

Do **not** set live production `docuflow-db` back to Free. It is paid Basic
(`0.1c-256mb` in git) with owner-reported backups. Downgrading to Free
removes that backup posture and reintroduces 30-day expiry.

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

Prefer the opt-in script. It prints host and database name (not the password),
refuses production-looking identities, and applies `0003` only when you set
`STAGING_MIGRATE=1` after `STAGING_DATABASE_CONFIRM` matches:

```bash
export STAGING_MIGRATE_VERIFY=1
export DATABASE_URL=...          # staging Postgres only
export STAGING_DATABASE_CONFIRM=docuflow_staging   # name or host/name
# inspect only (FAIL if pending):
python scripts/staging_migrate_verify.py
# apply pending upgrade after identity matches:
export STAGING_MIGRATE=1
python scripts/staging_migrate_verify.py
```

Manual equivalent:

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
   Do **not** run downgrade against a persistent staging database from an
   agent. Rollback tests stay on disposable local databases.

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

The test writes only `docuflow-test/<uuid>/probe.bin` and deletes that key
on success or failure. It fetches the presigned URL without logging it.
It skips when credentials are missing so CI stays green, and it fails if
`TEST_S3_BUCKET` matches `docuflow-documents` or `PRODUCTION_S3_BUCKET`.
Do not log the values. The application has no global key prefix, so a
**dedicated bucket** is required for staging/production isolation — a
prefix on a shared production bucket is not enough.

This procedure has **not** been executed from this environment.
Provider verified: **NOT EXECUTED — missing dedicated test credentials.**

## Staging smoke-test checklist

Owner-run mutating smoke **PASS** (7 Nov 2026, 09:35 Asia/Jakarta) against
`https://docuflow-staging-api.onrender.com`. Cross-user check **SKIPPED**.
Do not paste passwords into chat. Do not commit credentials.

The script prints `PASS`, `FAIL`, `SKIPPED`, or `NOT EXECUTED` per check.
Skipped extended checks are never counted as success. Exit 2 when
`STAGING_API_URL` is unset.

```bash
# Exits 2 with NOT EXECUTED when unset — safe for CI.
python scripts/staging_smoke.py
STAGING_API_URL=https://docuflow-staging-api.onrender.com python scripts/staging_smoke.py
```

Optional extended checks (dedicated staging test account and test PDF only).
These **modify staging data** and stay SKIPPED without `STAGING_SMOKE_MUTATIONS=1`.
Registration also needs `STAGING_SMOKE_REGISTER=1`. Non-loopback URLs need
`STAGING_HOST_CONFIRM` equal to the API hostname. Production hosts are refused.

```bash
export STAGING_API_URL=https://docuflow-staging-api.onrender.com
export STAGING_HOST_CONFIRM=docuflow-staging-api.onrender.com
export STAGING_WEB_URL=https://docuflow-staging-web.onrender.com
export STAGING_SMOKE_MUTATIONS=1
export STAGING_SMOKE_EMAIL=staging-probe@example.com
export STAGING_SMOKE_PASSWORD=...   # do not commit
export STAGING_SMOKE_REGISTER=1
export STAGING_SMOKE_PDF=./path/to/tiny-test.pdf
export STAGING_SMOKE_SECOND_EMAIL=staging-other@example.com
export STAGING_SMOKE_SECOND_PASSWORD=...
python scripts/staging_smoke.py
```

Owner manual checks after a real staging API exists:

| Step | What to confirm | Status here |
| --- | --- | --- |
| 1. API startup | Process stays up; fail-fast does not abort | Owner-reported live; `/health` PASS |
| 2. `GET /health` | HTTP 200, `status=ok` | **PASS** (agent + owner) |
| 3. `GET /ready` | HTTP 200 if DB+storage up; HTTP 503 if not | **PASS** |
| 4. PostgreSQL | `/ready` checks.database true | **PASS** |
| 5. Migration | `alembic current` is `0003_cost_efficient_reliability` | Owner Shell **PASS** (9.10D) |
| 6. Authentication | register/login on staging, CSRF cookie set | Owner login + `/v1/auth/me` **PASS** |
| 7. Document upload | PDF upload 200 for the staging user | Owner **PASS** |
| 8. Document processing | `extract_text` (or similar) job completes | Owner **PASS** |
| 9. File download | Owner can download; other user gets 403 | Owner download HTTP 302 **PASS**. Live B GET/download/DELETE **403** |
| 10. Background jobs | `JOB_BROKER=inline`; job leaves `queued` | **PASS** (`broker=inline`, job completed) |
| 11. Credit ledger | reserve then settle or refund once | **NOT EXECUTED** as a separate check |
| 12. Error handling | `/ready` 503 body has no DSN/signature | **NOT EXECUTED** (ready was 200) |
| 13. Worker/API | No paid worker in default staging stack | N/A (inline) |
| 14. S3 integration | Upload visible in the **staging** bucket only | `/ready` storage true; upload accepted. Bucket listing **NOT EXECUTED** |

## End-to-end staging verification procedure

This is an owner runbook. Hosted staging exists. Lifecycle smoke, hosted
Alembic inspect, and live cross-user isolation have owner evidence. This is
not production.

Free Render limitations to expect: web services spin down after about 15
minutes idle; the first request can take about a minute to wake; spin-down
kills in-flight **inline** jobs; there is no private networking between
Free web services; Free Postgres has no managed backups.

| Step | How | Status here |
| --- | --- | --- |
| 1. Render staging startup | Apply `infra/render.staging.yaml` in a dedicated workspace after owner approval. Confirm no `docuflow-api` / `docuflow-db` in that workspace. | **PROVISIONED** (owner) |
| 2. Database connectivity | `/ready` `checks.database=true` and `scripts/staging_migrate_verify.py` `SELECT 1` | `/ready` **PASS**. Owner Shell `SELECT 1` **PASS** |
| 3. Migration completion | Alembic current = `0003_cost_efficient_reliability` | Owner Shell **PASS** (`0003`, one head, no upgrade) |
| 4. S3 connectivity | `/ready` `checks.storage=true` plus optional `pytest -m provider` | `/ready` **PASS**. Provider test owner **PASS** |
| 5. API health | `GET /health` HTTP 200 | **PASS** |
| 6. API readiness | `GET /ready` HTTP 200 | **PASS** |
| 7. Frontend availability | `STAGING_WEB_URL` GET `/` HTTP 200 | **PASS** |
| 8. User authentication | smoke `STAGING_SMOKE_EMAIL` login / register | Owner login **PASS** |
| 9. Document upload | smoke `STAGING_SMOKE_PDF` `POST /v1/documents` | Owner **PASS** |
| 10. Document processing | smoke `extract_text` job completes (`JOB_BROKER=inline`) | Owner **PASS** |
| 11. Document download | owner `GET /v1/documents/{id}/download` | Owner HTTP 302 **PASS**. Live other-user **403**. Unauth **401** |
| 12. Cleanup execution | staging cron `python -m docuflow.cleanup` every 15 minutes; API `CLEANUP_INTERVAL_SECONDS=0` | Smoke `DELETE` **PASS**. Cron run **NOT EXECUTED** |
| 13. Queued-job recovery | existing Phase 9.6 `recover_queued_jobs` on API boot; limit remains 100. Free spin-down still kills `processing` rows until stale cleanup. | Implemented in code; **not staging verified** |

Do not introduce a new queue. Redis stays omitted on staging.

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

- `docuflow-web` Free, `docuflow-api` Free, `docuflow-db` `0.1c-256mb` (Basic in git), optional Free Redis in YAML (live production has **no** Redis)
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
| Successful Render deployment | **PRODUCTION VERIFIED** (9.12). Health + functional + isolation owner-run. Isolated restore drill **VERIFIED** (9.13B). Production recovery ready **YES** (no cutover) |
| Staging Blueprint | `infra/render.staging.yaml` applied in a dedicated workspace (9.10) |
| Staging migration `0003` | Owner Shell **PASS** (9.10D) on `docuflow_staging_db` |
| Production migration `0003` | Restore copy at 7 Nov 2026, 22:25: `0003_cost_efficient_reliability`. Live `docuflow-db` DSN still not opened |
| Live provider verification | Dedicated `TEST_S3_*` owner-run (6 Nov 2026). Production bucket `docuflowai-documents` (owner-reported) |

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

Production-specific restore, Alembic inspect, and isolated drill:
`docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md` (Phase 9.13).
Owner restored into isolated `docuflow-db-restore-drill-20261107`
(`dpg-dbnk595g1s2s73cuafl0-a` / `docuflow_db_q32a_d7gs`). Identity gate
**isolated-restore**. Owner PSQL: Alembic `0003`, required tables, counts
without error. Drill **VERIFIED**. Production was not cut over. Phase 9.14
cleanup of `docuflow-db-restore-drill-20261107` is **OWNER VERIFIED**
deleted (gone-from-list report 8 Nov 2026, 15:46 Asia/Jakarta; `docuflow-db`
still present). This agent did not click Delete
(`docs/reports/PHASE_9_14_RECOVERY_DRILL_CLEANUP.md`). Phase 9.15 backup/PITR
dashboard fields for `docuflow-db` are **NOT VERIFIED**
(`docs/reports/PHASE_9_15_BACKUP_PITR_ASSURANCE.md`). Phase 9.16 isolated
PITR instance `docuflow-rto-rpo-drill-20261108` is **OWNER-REPORTED**
Available (`dpg-dboq68bm8hqs73en0rpg-a`). T1−T0 15 min (owner clocks).
Owner PSQL Alembic `0003` and required tables **PASS**. RPO still
**NOT DETERMINABLE**. Drill instance **OWNER VERIFIED** deleted (18:19
Asia/Jakarta); `docuflow-db` still present. This agent did not click Delete
(`docs/reports/PHASE_9_16_RTO_RPO_RECOVERY_VALIDATION.md`). Do not restore
into `docuflow-db`.

This section is a general runbook. It was **not** executed against staging or
production from this environment. The Blueprint lists Postgres `0.1c-256mb`;
the **live** Render plan must still be read from the dashboard. Do not
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
