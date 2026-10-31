# Render.com deployment

This application is designed for Render, not a single serverless function. It needs:

1. Next.js web service
2. FastAPI web service
3. Background worker
4. PostgreSQL
5. Redis
6. External S3-compatible bucket (Cloudflare R2, AWS S3, or MinIO)

The Blueprint is `infra/render.yaml` (not the repo root). Web, API, Postgres,
and Redis/Key Value are set to Render **Free**. Background workers have no Free
compute plan, so `docuflow-worker` stays on `0.5c-512mb` (cheapest paid).

A Render deploy is still supported on this setup. Four of five resources are
Free. The worker is the only paid piece and is the reason Render may ask for a
payment method.

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
   and `docuflow-redis` should be **Free**. `docuflow-worker` will stay on
   **0.5 CPU / 512 MB**.
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

   Leave `DATABASE_URL` and `REDIS_URL` alone — Render injects them.
   Leave the `postgres://` URL as-is; the API rewrites it to psycopg3.

7. Apply the Blueprint. Render creates Postgres and Redis first, then builds
   API, worker, and web. The first Free web build can take several minutes;
   the first HTTP request after idle takes about a minute while the service
   wakes up.
8. After both web services have public URLs, set
   `DOCUFLOW_PUBLIC_WEB_URL`, `DOCUFLOW_PUBLIC_API_URL`,
   `DOCUFLOW_CORS_ORIGINS`, and `DOCUFLOW_TRUSTED_HOSTS` to the real
   `*.onrender.com` hosts, then redeploy the API (and web if you changed
   anything it reads).
9. Open the **web** URL, not the API URL. Health checks:
   `https://<api-host>/health` and `https://<api-host>/ready`.

### Fully Free (no worker bill)

If you do not want to add a card: in the Blueprint review, skip creating
`docuflow-worker`, and on `docuflow-api` set `JOB_BROKER=inline`. PDF jobs
then run inside the API process. That is slower and can time out on large
files, but the stack stays $0.

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
- Migrations: Render Free rejects `preDeployCommand`, so the API
  `startCommand` runs `alembic upgrade head` and then uvicorn. That is
  idempotent and safe on a single Free instance (including after spin-up).
  If you later scale the API on a paid plan, move migrations back to
  pre-deploy or a one-off job so replicas do not race.

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
