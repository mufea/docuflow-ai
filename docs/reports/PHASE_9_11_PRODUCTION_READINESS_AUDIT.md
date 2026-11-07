# Phase 9.11 — Production readiness audit and deployment planning

This is an **audit and plan**. It is **not** a production go-live, not an
authorization, and not a Blueprint apply.

No production resources were created. `infra/render.yaml` was **not** applied.
No migrations were executed. No application code was changed. No paid provider
calls were made.

## 1. Executive summary

Staging is **STAGING VERIFIED** (Phase 9.10D). Production is **not** ready to
deploy.

The application can run with `DOCUFLOW_ENV=production` (fail-fast for SQLite,
filesystem storage, weak secrets). That is **code** readiness, not a live
production system.

**Owner update (7 Nov 2026, 17:11 Asia/Jakarta), names only:**

| Question | Owner answer |
| --- | --- |
| Database service name | `docuflow-db` (production name, not `docuflow-staging-db`) |
| Workspace contains `docuflow-staging-*`? | **no** |
| “Paid plan name” as typed | `dpg-dbiqe70ae00c73cdif7g-a` — this is a Render **instance id/host**, not a plan slug (Basic/Pro/etc.) |
| Backups enabled | **no** |

Staging inspect used a **different** instance (`dpg-dbn71tec6qcc73cric9g-a` / `docuflow_staging_db`). These look like separate databases.

`infra/render.yaml` still lists `plan: free`. This agent did **not** apply it.

**Remaining blockers:**

1. **Backups disabled** on `docuflow-db` (CRITICAL for production data).
2. Paid **plan slug** still not named (instance id is not a plan).
3. Dedicated production object bucket / unique keys not confirmed.
4. Owner authorization to **deploy application services** is still absent.
5. Blueprint `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`; Free web SMTP egress blocked.
6. Free web spin-down still kills in-flight **inline** jobs.

**Recommendation: NO-GO** for production go-live. Workspace isolation and a
distinct `docuflow-db` are owner-reported progress. Enable backups before
any user data. Do **not** apply `infra/render.yaml`.

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
| `docuflow-db` | Postgres 16, YAML `plan: free` | YAML still Free. Owner reports a **paid** dashboard plan (**NOT VERIFIED**: which instance, backups on?) |
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
| P1 | CRITICAL | `docuflow-db` backups **disabled**. YAML still `plan: free`. Plan slug not provided. |
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
| YAML `plan: free` vs paid dashboard | CRITICAL | Do not sync YAML until it matches the paid plan slug; confirm backups |
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
| B Infra | Blueprint Postgres plan safe for prod data | YAML still Free (**FAIL** to sync). Live `docuflow-db` paid: owner-reported. Plan slug **NOT VERIFIED**. Backups **FAIL** (off) |
| B Infra | `infra/render.yaml` applied | **NOT VERIFIED** (must stay unapplied) |
| C Security | Unique prod secret/keys | **BLOCKED** |
| C Security | Prod isolation tested | **NOT VERIFIED** |
| D Data | Dedicated prod bucket | **BLOCKED** |
| D Data | Managed or operator backups | **FAIL** (owner: backups enabled **no**) |
| E Providers | Live AI | **NOT APPLICABLE** until owner enables |
| E Providers | Real email | **FAIL** on Free web + console |
| F Ops | Runbook exists | PASS (docs) |
| F Ops | Backup executed | **NOT VERIFIED** |
| G Cost | Owner accepted paid Postgres | Owner-reported **PASS** for `docuflow-db` (`dpg-dbiqe70ae00c73cdif7g-a`) |
| H Auth | Owner production approval | **NOT AUTHORIZED** |

A GO for **deploy** requires every CRITICAL item PASS plus explicit owner
approval. That is **not** met.

## 16. Owner action items

1. Do **not** apply `infra/render.yaml`. YAML still says Free Postgres.
2. **Enable backups** on `docuflow-db` in the Render dashboard (or confirm
   the paid tier’s backup product and turn it on). Do not paste DSNs.
3. Optionally reply with the **plan slug** as shown next to the instance
   (for example Basic / Pro), not the `dpg-…` id. Not required to enable backups.
4. Dedicated production bucket + unique keys (not staging). Never paste values.
5. Decide: inline vs RQ; mock vs live AI; console vs SMTP.
6. Explicit written authorization is still required before deploying API/web.

## 17. Evidence limitations

- No production host was contacted.
- No Render production dashboard was inspected.
- Paid pricing is APPROXIMATE.
- No dependency CVE scan this phase.
- No production pentest.
- Staging success does not prove production isolation or backups.

## 18. Final recommendation

**NO-GO** — `docuflow-db` exists in a workspace without staging services, and
the owner reports it is paid, but **backups are off**. YAML still says Free.
Bucket/keys, email/AI, and deploy authorization remain outstanding.

The product is **staging-verified**. It is **not** production-deployed,
**not** production-verified, and **not** production-authorized.
