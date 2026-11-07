# Phase 9.11 — Production readiness audit and deployment planning

This started as an **audit and plan**. On 7 Nov 2026, 17:42 Asia/Jakarta the
owner sent `Authorize production deploy, keep inline`.

This agent **did not** apply `infra/render.yaml`. Owner commit `4f1f07e`
(7 Nov 2026, 17:53 Asia/Jakarta) set `docuflow-db` `plan: 0.1c-256mb`.
This agent did not create Render services. Owner public hosts are **live**
(read-only evidence). Keep `JOB_BROKER=inline`. Do **not** add Redis or a
worker.

## 1. Executive summary

Staging is **STAGING VERIFIED** (Phase 9.10D). Production API and CMS
**respond** on owner custom domains. Production is **not** functionally
verified (no login/upload/isolation on production).

The application can run with `DOCUFLOW_ENV=production` (fail-fast for SQLite,
filesystem storage, weak secrets). Live hosts are **not** the same as
production functional verification.

**Owner updates (names only):**

| Question | Owner answer | When (Asia/Jakarta) |
| --- | --- | --- |
| Database service name | `docuflow-db` | 7 Nov 2026, 17:11 |
| Workspace contains `docuflow-staging-*`? | **no** | 17:11 |
| Instance id | `dpg-dbiqe70ae00c73cdif7g-a` | 17:11 |
| Plan (display name) | **Basic** | 17:23 |
| Backups enabled | **yes** | 17:23 |
| Production bucket name | `docuflowai-documents` | 17:33 |
| Production S3 keys unique (not staging) | **yes** | 17:37 |
| Production deploy authorization | **yes**, keep **inline** | 17:42 |
| Production API URL | `https://docuflowai.site` | 18:00 |
| Production CMS / web URL | `https://docuflowai.online` | 18:00 |
| Redis / worker appeared? | **no** | 18:05 |
| Cleanup cron running? | **yes** | 18:14 |

Staging inspect used a **different** instance (`dpg-dbn71tec6qcc73cric9g-a`).
Git Blueprint Postgres plan is now `0.1c-256mb` (`origin/main` `4f1f07e`).
That matches the owner-reported **Basic** dashboard plan. The file was **not**
applied from this agent.

Bucket name isolation (names only): `docuflowai-documents` is **not**
`docuflow-staging`, **not** `docuflow-provider-test`, and **not** the code
default `docuflow-documents`. Owner reports production S3 keys are **unique**
(not staging). Values were not received.

**Remaining blockers (post-live-hosts):**

1. Production mutating smoke / cross-user isolation **not** run.
2. Mock AI + console email; Free web SMTP egress blocked (accepted unless owner changes it).
3. Free web spin-down still kills in-flight inline jobs.

**Recommendation:** public hosts are **live** (inline). Do **not** Blueprint-sync
Redis. Do **not** point `STAGING_*` at production. Functional production
verification still **NO**.

## 2. Verified baseline (staging, not production)

From `docs/reports/PHASE_9_10D_OWNER_VERIFICATION.md` and
`docs/IMPLEMENTATION_STATUS.md`. Not re-tested in this phase.

| Item | Staging evidence |
| --- | --- |
| API / web / db / cleanup | Live (`docuflow-staging-*`) |
| Redis / worker | Absent (expected) |
| Broker | `inline` |
| AI / email | mock / console |
| `/health` `/ready` frontend | PASS |
| Auth, upload, `extract_text`, download 302, delete | PASS |
| Alembic | `0003_cost_efficient_reliability`, one head, no inspect-time mutation |
| Cross-user | GET/download/DELETE 403; unauth GET 401 |

Treat this as **staging** evidence only.

## 3. Repository and commit evidence

| Item | Value |
| --- | --- |
| Repository | https://github.com/mufea/docuflow-ai |
| Expected `origin/main` | `bed3b61` |
| Actual `origin/main` | `bed3b61ad05f411cee56e6854f60045a77061d3a` |
| Subject | Merge pull request #20 (Phase 9.10D) |
| Merge time | 7 Nov 2026, 15:22 Asia/Jakarta |
| Audit time | 7 Nov 2026, 15:42 Asia/Jakarta |
| Production deploy | **NOT EXECUTED** |
| Production authorization | **NOT AUTHORIZED** |

Working tree at audit start: clean. This phase adds documentation only.

## 4. Production architecture assessment

### A. Web (`docuflow-web`)

Next.js app. Blueprint: Node, Free, `corepack pnpm --filter web build/start`,
health `/`. `NEXT_PUBLIC_API_BASE=/v1`. `API_INTERNAL_URL` is the **public**
API URL (`RENDER_EXTERNAL_URL`); Free web services have **no private
networking**. Sessions are API cookies (`df_session`, `df_csrf`), Secure +
SameSite lax in production. CSRF required on mutating API calls.

Gaps: custom domain must be added to `DOCUFLOW_TRUSTED_HOSTS` and CORS.
Production cookie domain for a custom host is **NOT VERIFIED**.

### B. API (`docuflow-api`)

FastAPI/uvicorn. Boot: `python -m docuflow.migrate && uvicorn`. Fail-fast via
`production_readiness_errors`. Pool: SQLAlchemy `pool_size=5`,
`max_overflow=10`, `pool_pre_ping=True`. In-memory rate limiter (per process;
lost on sleep). `/health` liveness; `/ready` checks database, storage, and
Redis only if `JOB_BROKER=rq`.

Upload default 50 MiB / 400 pages. Download: owned docs only; S3 is HTTP 302
to a 600s signed URL. Isolation: `get_owned` 403 for other users (staging
verified). JSON logs when `LOG_JSON=true`.

Gaps: no shared rate-limit store; no APM; Postgres SSL mode not explicitly
forced in code (**NOT VERIFIED**).

### C. Database

PostgreSQL 16 + Alembic. Head `0003_cost_efficient_reliability`. Schema is
staging-verified. Production Blueprint still uses **Free** Postgres: no
managed backups, 30-day expiry. That plan is a **CRITICAL** production data
risk. Advisory lock `86420138` serializes boot migrations.

### D. Object storage

`STORAGE_BACKEND=s3` required in production. PutObject uses
`ServerSideEncryption=AES256`. Signed GET, owned delete + retry queue.
**Dedicated production bucket and keys are required.** Staging
`docuflow-staging` and provider-test buckets must not be reused. Prefix
isolation on a shared bucket is **not** sufficient (documented). Lifecycle
and versioning: **owner/provider configuration, NOT VERIFIED**.

### E. Jobs

Default `JOB_BROKER=inline`. Idempotency keys on jobs and credit ledger.
Stale job recovery on API boot (limit 100). Cleanup cron every 15 minutes.
RQ worker is optional (`infra/render.scaling.yaml`, paid). Redis in the
production Blueprint is unused while inline.

**Minimal production:** keep inline. Accept that Free/sleeping API dies
mid-job; stale cleanup recovers `queued`/`processing` later.

**Scalable production:** `JOB_BROKER=rq` + paid worker + Redis. Use only with
workload that needs background durability. Do not add Redis/worker only to
“look production-ready.”

### F. AI

`AI_PROVIDER=mock` in Blueprint. Live path: `openai_compatible` + `AI_API_KEY`
+ base URL/model + timeout. Credits/ledger exist. No production AI keys
audited. Do not enable until owner accepts cost, privacy, and timeout
behavior. **Do not copy staging (there are no live AI keys there).**

### G. Email

`EMAIL_BACKEND=console` logs only. SMTP backend exists (`SMTP_HOST`, STARTTLS).
Free Render web **cannot** egress SMTP 25/465/587. Real registration/reset
mail needs a paid web instance or an HTTPS mail API (not implemented).
SPF/DKIM/DMARC: **owner DNS, NOT VERIFIED**.

## 5. Infrastructure assessment (`infra/render.yaml` — inspect only)

| Resource | Blueprint | Production-safe as written? |
| --- | --- | --- |
| `docuflow-web` | web, Free | Limited (spin-down, 750 h/mo) |
| `docuflow-api` | web, Free | Limited (spin-down kills inline jobs) |
| `docuflow-db` | Postgres 16, YAML `0.1c-256mb` | Matches owner Basic. Backups owner-reported yes. **Not applied** from this agent |
| `docuflow-redis` | Free Key Value | Unused while inline; data lost on restart |
| `docuflow-cleanup` | cron `*/15` | Acceptable scheduler |
| Worker | omitted | Correct for inline |

**Do not apply this file.** Syncing it into the **staging** workspace would
create production-named services beside staging or collide. Production needs
a **separate** workspace with **no** `docuflow-staging-*` and **no** reuse of
staging DSN/bucket/keys.

Proposed (plan only, not applied): paid Postgres with backups; keep inline
unless load requires RQ; omit Redis until `JOB_BROKER=rq`; dedicated S3/R2
bucket; unique `DOCUFLOW_SECRET_KEY`; SMTP only on a plan that allows it.

## 6. Security findings

Static review only. **Not a penetration test.**

| ID | Severity | Finding |
| --- | --- | --- |
| P1 | HIGH | Full Blueprint still includes unused Redis. Postgres plan in git is `0.1c-256mb`. Do not add a worker. |
| P2 | HIGH | No production workspace/bucket/secrets exist; reuse of staging would mix data. |
| P3 | HIGH | Free API spin-down interrupts inline jobs; rate limits reset in memory. |
| P4 | HIGH | Console email; SMTP blocked on Free web. Password reset unusable for real users. |
| P5 | MEDIUM | Production CORS regex allows `https://*.onrender.com`. Tighten for a custom domain. |
| P6 | MEDIUM | Other-user access is 403 (existence leak vs 404). Existing policy. |
| P7 | MEDIUM | `role=admin` bypasses document/job ownership. |
| P8 | MEDIUM | Signed download URLs (600s) are bearer capabilities if leaked. |
| P9 | LOW | In-process rate limiter is per-instance. |
| P10 | LOW | Mock AI / console email are fail-open product modes, warned at boot. |
| P11 | INFORMATIONAL | Staging isolation tests passed; production isolation **NOT VERIFIED**. |
| P12 | INFORMATIONAL | Dependency CVE scan **NOT VERIFIED** this phase. |

Upload type/size checks and path-sanitization tests exist locally. SQL access
is via SQLAlchemy bound parameters in reviewed services.

## 7. Environment variable inventory (names only)

Never copy staging values into production.

| Name | Purpose | Req | Source | Secret | Verify |
| --- | --- | --- | --- | --- | --- |
| `DOCUFLOW_ENV` | Fail-fast mode | Yes | Blueprint `production` | No | Boot without SQLite |
| `DATABASE_URL` | Postgres | Yes | **New** prod DB only | Yes | `/ready` database; never print |
| `STORAGE_BACKEND` | Must be `s3` | Yes | Blueprint | No | Fail-fast |
| `S3_BUCKET` | Prod bucket | Yes | Owner, not staging | No | HeadBucket; name isolation |
| `S3_ACCESS_KEY_ID` | Prod key | Yes | Owner unique key | Yes | Presence only |
| `S3_SECRET_ACCESS_KEY` | Prod secret | Yes | Owner unique key | Yes | Presence only |
| `S3_ENDPOINT_URL` | R2/MinIO | If not AWS | Owner | No | `/ready` storage |
| `S3_REGION` | Region | Yes | `auto` or provider | No | Provider docs |
| `S3_FORCE_PATH_STYLE` | Path-style | Yes for R2 | Blueprint | No | — |
| `DOCUFLOW_SECRET_KEY` | Sessions | Yes | `generateValue` unique | Yes | Length ≥32 |
| `JOB_BROKER` | `inline` or `rq` | Yes | Owner decision | No | `/ready` broker |
| `REDIS_URL` | RQ only | If `rq` | New KV | Yes | Only if rq |
| `COOKIE_SECURE` | HTTPS cookies | Yes | Forced in prod | No | Set-Cookie |
| `COOKIE_SAMESITE` | CSRF | Yes | `lax` | No | — |
| `DOCUFLOW_PUBLIC_API_URL` | Links | Yes | Render URL | No | Auth emails |
| `DOCUFLOW_PUBLIC_WEB_URL` | CORS/links | Yes | Web URL | No | CSRF origin |
| `DOCUFLOW_CORS_ORIGINS` | CORS | Yes | Web URL | No | Browser |
| `DOCUFLOW_TRUSTED_HOSTS` | Host header | Yes | Add custom domain | No | 400 on bad Host |
| `AI_PROVIDER` | mock / live | Yes | Owner | No | Boot warning if mock |
| `AI_API_KEY` | Live AI | If live | Owner | Yes | Do not test in this phase |
| `AI_BASE_URL` / `AI_MODEL` | Live AI | If live | Owner | No | — |
| `EMAIL_BACKEND` | console / smtp | Yes | Owner | No | — |
| `SMTP_HOST` / `PORT` / `USERNAME` / `PASSWORD` / `SMTP_FROM` | Mail | If smtp | Owner; needs non-Free egress | Yes (password) | Do not send test mail here |
| `LOG_JSON` / `LOG_LEVEL` | Observability | Yes/opt | Blueprint | No | Log sample |
| `CLEANUP_INTERVAL_SECONDS` | Must stay `0` with cron | Yes | Blueprint | No | — |
| `STRIPE_*` / `MIDTRANS_*` | Billing | Optional | Owner | Yes | Unset = payments off |

`TEST_S3_*` is **not** a production variable.

## 8. AI / email provider readiness

| Item | Status |
| --- | --- |
| Mock AI | Implemented; production Blueprint default |
| Live AI | Code exists; **NOT VERIFIED**; cost/privacy owner decision |
| Console email | Implemented; not user-viable |
| SMTP | Implemented; **blocked on Free web egress** |
| SPF/DKIM/DMARC | **NOT VERIFIED** |

## 9. Database and storage readiness

| Item | Status |
| --- | --- |
| Schema head `0003` | Staging **PASS**; production DB **does not exist** |
| Production Postgres plan | Blueprint Free = **FAIL** for real data |
| Managed backups | **FAIL** on Free; paid plan **NOT VERIFIED** |
| Dedicated prod bucket | **BLOCKED** (not provisioned) |
| Staging/prod isolation | **Required**, not yet done |

## 10. Queue / worker decision

**Recommend keep `JOB_BROKER=inline`** for first production, matching verified
staging, unless the owner has a measured need for background durability.

Do **not** add Redis or a paid worker by default. Redis in `infra/render.yaml`
is unused while inline; staging correctly omitted it.

Add RQ only when: paid worker budget exists, jobs outlive HTTP, and owner
accepts Redis as a new failure domain.

## 11. Operational cost scenarios (APPROXIMATE)

Pricing below is **not a quote**. Render Free limits were recorded in
`docs/DEPLOYMENT.md` on 5 Nov 2026. Paid list prices must be confirmed on
the Render/R2 dashboards before purchase. **Do not purchase in this phase.**

### 1. Minimal (reject for real users)

- Components: 2× Free web, Free Postgres, cleanup cron, R2, inline, mock AI, console email.
- Infra: ~$0 Render + R2 usage.
- Limits: 30-day DB expiry, no DB backups, spin-down, 750 instance hours, no SMTP.
- **Not acceptable for production customer data.**

### 2. Recommended first production

- Components: 2× **paid** web (avoid spin-down if jobs matter), **paid Postgres with backups**, cleanup cron, dedicated R2 bucket, inline broker, **no** Redis, **no** worker. SMTP only if the web plan allows egress (or keep mock/console and accept no mail).
- Infra: **APPROXIMATE** tens of USD/month (commonly two Starter web + Basic Postgres; confirm current list). R2 usually cents–low dollars at low volume.
- Main cost risks: instance hours, Postgres plan, AI if enabled later, storage egress.

### 3. Scalable

- Recommended plus `JOB_BROKER=rq`, paid `docuflow-worker` (`0.5c-512mb` in scaling overlay), Redis (Free KV or paid).
- Extra: paid worker (Render has no Free worker) + Redis ops complexity.
- Use when queue latency/durability is a measured need.

AI tokens and Stripe fees are **usage** costs, not Render, and are zero while mock/unset.

## 12. Backup and disaster recovery

**Implemented:** object delete retry; job credit refunds; API boot queued-job
recovery; Render deploy rollback of **code** (not data).

**Not implemented as managed prod backups:** Free Postgres has none. No
automated `pg_dump` cron in the Blueprint (by design).

**Proposed (not executed):**

| Objective | Free Blueprint | Recommended paid |
| --- | --- | --- |
| RPO | Unbounded (instance loss = data loss) | Daily `pg_dump` or vendor PITR (confirm plan) |
| RTO | Hours to rebuild empty | Hours: restore dump to new DB, point API, `/ready` |
| Objects | Provider versioning **NOT VERIFIED** | Enable versioning on **prod** bucket |
| Queue | N/A (inline) | Redis ephemeral; jobs in Postgres |
| Rollback | Redeploy previous Render build | Schema downgrade is **not** automatic; restore dump |
| Secrets | Rotate S3 keys and `DOCUFLOW_SECRET_KEY` (invalidates sessions) | Same |

## 13. Deployment sequence (PLAN ONLY)

Do not execute.

**A. Infrastructure preparation** — Dedicated prod workspace (no staging
names). Paid Postgres. Dedicated bucket. Unique keys. Stop if any staging
identifier appears.

**B. Configuration** — Fill `S3_*`, let `DOCUFLOW_SECRET_KEY` generate, keep
`JOB_BROKER=inline` unless decided otherwise. Do not enable live AI/Stripe
until needed. SMTP only on a plan that can send mail.

**C. Pre-deploy** — Confirm names `docuflow-api` / `docuflow-db` (not
staging). Confirm Alembic head on empty prod DB **after** owner approval to
migrate. Storage HeadBucket. Backup plan exists **before** user data.

**D. Controlled deploy** — Apply Blueprint only in the prod workspace after
written owner approval. Order: Postgres → API (migrate on boot) → web → cron.
Smoke `/health` `/ready` then mutating checks with **prod test accounts**,
not staging users. Stop on fail-fast, 503 ready, or isolation failure.

**E. Post-deploy** — Repeat 9.10D matrix against production hosts only after
authorization. Confirm backups. Production remains unverified until that
evidence exists.

Rollback: previous Render deploy. Data: restore dump to a **new** database,
never a blind in-place overwrite from this agent.

## 14. Risk register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Apply YAML onto staging workspace | CRITICAL | Separate workspace; refuse if `docuflow-staging-*` present |
| Blueprint Redis vs inline | HIGH | Do not create Redis/worker; link new services to existing `docuflow-db` |
| Staging bucket/keys in prod | CRITICAL | New bucket and keys; preflight isolation |
| Inline job + spin-down | HIGH | Paid always-on API or accept stale recovery |
| Console email | HIGH | SMTP on paid egress, or accept no mail |
| Live AI cost | HIGH | Keep mock until budget exists |
| Blueprint Redis unused | LOW | Omit until RQ |
| Sync deleting existing worker | HIGH | Comment in YAML; do not sync into a workspace that already has `docuflow-worker` |

## 15. GO / NO-GO checklist

| Area | Item | Status |
| --- | --- | --- |
| A Code | Fail-fast production settings | PASS (code) |
| A Code | AuthN/Z + isolation tests | PASS (staging + local) |
| A Code | Alembic single head `0003` | PASS (staging inspect) |
| B Infra | Production workspace exists | Owner-reported **PASS** (no `docuflow-staging-*`) |
| B Infra | Live Postgres plan + backups | Owner-reported **PASS** (Basic, backups yes). Git YAML `0.1c-256mb` |
| B Infra | `infra/render.yaml` applied | **NO** — not applied from this agent |
| B Infra | Public API + CMS respond | **PASS** (read-only, 18:00 Asia/Jakarta) |
| C Security | Unique prod S3 keys | Owner-reported **PASS** (not staging). Values not seen. `DOCUFLOW_SECRET_KEY` still generate-on-deploy |
| C Security | Prod isolation tested | **NOT VERIFIED** |
| D Data | Dedicated prod bucket | Owner-reported **PASS** (`docuflowai-documents`; not staging/test/default) |
| D Data | Managed or operator backups | Owner-reported **PASS** (enabled). Restore drill **NOT VERIFIED** |
| E Providers | Live AI | **NOT APPLICABLE** until owner enables |
| E Providers | Real email | **FAIL** on Free web + console |
| F Ops | Runbook exists | PASS (docs) |
| F Ops | Backup executed | **NOT VERIFIED** |
| G Cost | Owner accepted paid Postgres | Owner-reported **PASS** for `docuflow-db` (`dpg-dbiqe70ae00c73cdif7g-a`) |
| H Auth | Owner production approval | **YES** (17:42 Asia/Jakarta, `JOB_BROKER=inline` only) |

A GO for **agent-applied Blueprint** is still **NO**. A GO for **owner
manual service create** against existing `docuflow-db` is **YES** (inline).

## 16. Owner action items

1. **Do not** full-sync `infra/render.yaml` (it still defines unused Redis).
2. Redis/worker owner-reported **absent**. Cleanup cron owner-reported **running**.
3. Do **not** point `STAGING_*` at `docuflowai.site` / `docuflowai.online`.
4. Mock AI and console email stay unless you authorize otherwise.

## 17. Evidence limitations

- Production hosts were contacted **read-only** (GET/OPTIONS). No login or mutations.
- No Render production dashboard was inspected.
- Paid pricing is APPROXIMATE.
- No dependency CVE scan this phase.
- No production pentest.
- Staging success does not prove production isolation or backups.

## 18. Final recommendation

**AUTHORIZED, LIVE HOSTS, NOT VERIFIED.** Inline broker on
`https://docuflowai.site`. CMS `https://docuflowai.online`. Agent did not
apply Blueprint. Production verification is still **NO**.

## 19. Owner deploy procedure (do not Blueprint-sync)

Workspace: the one with `docuflow-db` and **no** `docuflow-staging-*`.
Broker: `JOB_BROKER=inline`. Do **not** create Redis or `docuflow-worker`.

**Stop if** you see staging service names, staging bucket `docuflow-staging`,
or a prompt to change `docuflow-db` to Free.

### A. `docuflow-api` (web service, Python)

- Repo: `mufea/docuflow-ai`, branch `main` (or the commit you intend).
- Build: `pip install -r requirements.txt`
- Start: `python -m docuflow.migrate && uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT`
- Health: `/health`
- Env (names; do not paste secrets into chat):
  - `DOCUFLOW_ENV=production`
  - `DATABASE_URL` from **existing** `docuflow-db` (internal connection)
  - `JOB_BROKER=inline` (no `REDIS_URL` required)
  - `STORAGE_BACKEND=s3`, `S3_FORCE_PATH_STYLE=true`, `S3_REGION=auto`
  - `S3_BUCKET=docuflowai-documents`
  - `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_ENDPOINT_URL` = production unique keys
  - `DOCUFLOW_SECRET_KEY` = generate unique (do not copy staging)
  - `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`, `LOG_JSON=true`
  - `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`, `OCR_ENABLED=true`
  - `CLEANUP_INTERVAL_SECONDS=0`, `JOB_STALE_MINUTES=90`
  - After web exists: `DOCUFLOW_PUBLIC_WEB_URL` and `DOCUFLOW_CORS_ORIGINS` = web URL
  - `DOCUFLOW_TRUSTED_HOSTS=.onrender.com`
  - `DOCUFLOW_PUBLIC_API_URL` = this service’s public URL

Boot runs `python -m docuflow.migrate` against production Postgres. That is
expected on first API start.

### B. `docuflow-web` (web service, Node)

- Build: `corepack pnpm install --frozen-lockfile && corepack pnpm --filter web build`
- Start: `corepack pnpm --filter web start -p $PORT`
- Health: `/`
- `NODE_ENV=production`
- `API_INTERNAL_URL` and `DOCUFLOW_PUBLIC_API_URL` = API public URL
- `NEXT_PUBLIC_API_BASE=/v1`

### C. `docuflow-cleanup` (cron `*/15 * * * *`)

- Same Python build as API
- Start: `python -m docuflow.migrate && python -m docuflow.cleanup`
- Same `DATABASE_URL` (`docuflow-db`) and same production `S3_*` as the API
- `CLEANUP_LEASE_MINUTES=5`, `STORAGE_DELETE_MAX_ATTEMPTS=8`

### D. After first boot

Owner replied (18:00 Asia/Jakarta):

- API: `https://docuflowai.site`
- CMS: `https://docuflowai.online`
- Redis / worker: **no** (18:05 Asia/Jakarta)
- Cleanup cron: **running** (18:14 Asia/Jakarta)

Read-only evidence: `docs/reports/PHASE_9_11_PRODUCTION_LIVE_EVIDENCE.md`.
Do **not** paste DSNs or keys. Do **not** point `STAGING_*` at production.
