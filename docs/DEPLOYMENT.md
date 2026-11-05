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

Free limits that matter here: web services spin down after 15 minutes idle and
wake in about a minute; Free Postgres is 1 GB, one per workspace, and expires
after 30 days; Free Key Value is in-memory only and loses data on restart.

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
`STORAGE_DELETE_LEASE_MINUTES` (default 5). Alembic revision
`0003_cost_efficient_reliability` adds lease timestamps on `cleanup_leases`
and reclaim fields on `storage_deletions`. Do not run that migration against
production from this environment.

Keep `OCR_ENABLED=true`. Native Render Python images do not include Tesseract;
OCR uses the bundled RapidOCR ONNX engine in that case. Tesseract is used when
it is present on PATH.

Optional: SMTP, Stripe, Midtrans, `AI_API_KEY`.

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
| Live provider verification | **Not performed** — requires authorization |

## Health

- `/health` liveness (no dependency checks)
- `/ready` checks database, Redis when `JOB_BROKER=rq`, and object storage
  (`head_bucket` or a writable local directory). It does not echo secrets.

## Object storage

Do not store uploads on the Render disk. Configure R2 or S3 before enabling public sign-ups.

## Rollback

Render keeps previous deploys. Roll back the web, API, and worker together if the API schema changed. Database downgrades are not automatic; restore from a Postgres backup if a migration must be undone.

## HTTPS and domains

Terminate TLS at Render. Point the custom domain at the web service and set `DOCUFLOW_PUBLIC_WEB_URL` accordingly. The web service proxies `/v1` to the API so cookies stay first-party.
