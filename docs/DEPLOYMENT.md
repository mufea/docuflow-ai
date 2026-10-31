# Render.com deployment

This application is designed for Render, not a single serverless function. It needs:

1. Next.js web service
2. FastAPI web service
3. Background worker
4. PostgreSQL
5. Redis
6. External S3-compatible bucket (Cloudflare R2, AWS S3, or MinIO)

The Blueprint is `infra/render.yaml`. Web, API, Postgres, and Redis/Key Value
are set to Render **Free**. Background workers have no Free compute plan, so
`docuflow-worker` stays on `0.5c-512mb` (cheapest paid).

Free limits that matter here: web services spin down after 15 minutes idle and
wake in about a minute; Free Postgres is 1 GB, one per workspace, and expires
after 30 days; Free Key Value is in-memory only and loses data on restart.

## Changing existing Render services to Free

Editing this repo does not move live services by itself. After you pull and
push to the repo Render deploys from:

1. In the Render dashboard, open the Blueprint (or **New → Blueprint** and
   point it at `infra/render.yaml`), then sync / apply.
2. If a service is still on Starter or Basic after the sync, open it →
   **Settings** (or **Info** for datastores) → **Instance type** / **Plan** →
   **Free** → save.
3. Do this for `docuflow-web`, `docuflow-api`, `docuflow-db`, and
   `docuflow-redis`. Leave `docuflow-worker` on the smallest paid plan — Render
   will reject Free for a worker.
4. Confirm Billing shows $0 for those four resources. A Free workspace still
   needs a payment method if you keep the worker.

Render keeps the current plan when a Blueprint omits `plan`. This file now
sets `plan` explicitly. A Blueprint apply still will not recreate a datastore
just to change its plan; use the dashboard if Postgres or Redis stay paid.

## Status

| Checkpoint | Status |
| --- | --- |
| Local development | Supported |
| Automated tests | See `docs/IMPLEMENTATION_STATUS.md` |
| Render configuration | Blueprint present; validate in the Render dashboard |
| Successful Render deployment | **Not performed** |
| Live provider verification | **Not performed** — requires authorization |

Do not treat the Blueprint as a completed production deploy.

## Build and start

- Web: `pnpm install --frozen-lockfile && pnpm --filter web build` then `pnpm --filter web start -p $PORT`
- API: `pip install .` then `uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT`
- Worker: `python -m docuflow.worker`
- Migrations: API `preDeployCommand` runs `alembic upgrade head` **once per deploy**, not in the worker or extra API replicas. If you scale the API, keep migrations on pre-deploy / a one-off job.

## Required production environment

See `.env.example`. At minimum:

- `DOCUFLOW_ENV=production`
- `DOCUFLOW_SECRET_KEY` (long random)
- `DATABASE_URL` (Render Postgres). Leave the injected `postgres://` value as-is.
  The API and Alembic rewrite it to `postgresql+psycopg://` so SQLAlchemy uses
  psycopg3. Do not install `psycopg2`.
- `REDIS_URL`
- `JOB_BROKER=rq`
- `STORAGE_BACKEND=s3` plus bucket credentials
- `COOKIE_SECURE=true`
- `DOCUFLOW_PUBLIC_WEB_URL` / `DOCUFLOW_PUBLIC_API_URL`
- `DOCUFLOW_CORS_ORIGINS` and `DOCUFLOW_TRUSTED_HOSTS`

Optional: SMTP, Stripe, Midtrans, `AI_API_KEY`.

## Health

- `/health` liveness
- `/ready` checks database (and Redis when `JOB_BROKER=rq`) without echoing secrets

## Object storage

Do not store uploads on the Render disk. Configure R2 or S3 before enabling public sign-ups.

## Rollback

Render keeps previous deploys. Roll back the web, API, and worker together if the API schema changed. Database downgrades are not automatic; restore from a Postgres backup if a migration must be undone.

## HTTPS and domains

Terminate TLS at Render. Point the custom domain at the web service and set `DOCUFLOW_PUBLIC_WEB_URL` accordingly. The web service proxies `/v1` to the API so cookies stay first-party.
