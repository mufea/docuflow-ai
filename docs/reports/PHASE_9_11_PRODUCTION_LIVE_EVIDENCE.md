# Phase 9.11 — Production live hosts (read-only)

Owner-provided public URLs. This agent ran **read-only** GET/OPTIONS only.
No login, upload, delete, migrate, or Blueprint apply. No secrets recorded.

## 1. Owner hosts

| Role | Owner value | Normalized | When (Asia/Jakarta) |
| --- | --- | --- | --- |
| API | `https://docuflowai.site` | `https://docuflowai.site` | 7 Nov 2026, 18:00 |
| CMS / web | `docuflowai.online` | `https://docuflowai.online` | 7 Nov 2026, 18:00 |

These are **not** staging hosts (`docuflow-staging-api.onrender.com` /
`docuflow-staging-web.onrender.com`). Owner (18:05 Asia/Jakarta): **no
Redis / worker**. Owner (18:14 Asia/Jakarta): cleanup cron **is running**.

## 2. Read-only probes

Probed 7 Nov 2026, 18:00–18:01 Asia/Jakarta (WIB). TLS verified.
Cloudflare in front of Render. API origin `x-render-origin-server: uvicorn`.
CMS origin `x-powered-by: Next.js`.

| Check | URL | Result |
| --- | --- | --- |
| GET `/health` | `https://docuflowai.site/health` | **PASS** HTTP 200 `{"status":"ok","service":"docuflow-api"}` |
| GET `/ready` | `https://docuflowai.site/ready` | **PASS** HTTP 200 `status=ready` `broker=inline` `rq_workers=0` `checks.database=true` `checks.storage=true` `checks.redis=true` |
| GET `/` | `https://docuflowai.site/` | HTTP 404 FastAPI `{"detail":"Not Found"}` (API has no root page) |
| GET `/v1/auth/me` (no cookie) | `https://docuflowai.site/v1/auth/me` | **PASS** HTTP 401 `unauthenticated` |
| OPTIONS CORS | `https://docuflowai.site/v1/auth/me` Origin `https://docuflowai.online` | **PASS** `access-control-allow-origin: https://docuflowai.online` credentials true |
| GET `/` CMS | `https://docuflowai.online/` | **PASS** HTTP 200 HTML `title` DocuFlow AI (Next.js) |
| GET `/login` CMS | `https://docuflowai.online/login` | **PASS** HTTP 200 Next.js |
| GET `/health` via CMS rewrite | `https://docuflowai.online/health` | **PASS** same API health JSON (web `next.config.ts` rewrites `/health` and `/ready`) |
| GET `/ready` via CMS rewrite | `https://docuflowai.online/ready` | **PASS** same ready payload (`broker=inline`) |
| GET `/v1/auth/me` via CMS | `https://docuflowai.online/v1/auth/me` | **PASS** HTTP 401 (web `/v1` proxy) |
| TLS API | `docuflowai.site` | **PASS** CN/SAN `docuflowai.site` (Google Trust Services WE1) |
| TLS CMS | `docuflowai.online` | **PASS** CN/SAN `docuflowai.online` (Google Trust Services WE1) |

`checks.redis=true` with `broker=inline` is the **inline default** (no Redis
ping). It is **not** evidence that `docuflow-redis` exists. `rq_workers=0`
is consistent with no RQ worker.

## 3. What this does **not** prove

- Login, upload, extract, download, or delete on production
- Cross-user isolation on production
- Hosted Alembic head on production Postgres
- Restore drill / backups actually restorable
- Live AI or real email (still expected mock/console)

Do **not** point `STAGING_*` at these hosts. Staging smoke now refuses
`docuflowai.site` and `docuflowai.online`.

## 4. Status

PRODUCTION AUTHORIZED: **YES** (inline only).
PRODUCTION DEPLOYED: **YES** (public API + CMS respond).
PRODUCTION VERIFIED: **NO** (read-only only).
