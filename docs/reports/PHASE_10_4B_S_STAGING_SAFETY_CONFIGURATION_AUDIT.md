# Phase 10.4B-S — Staging safety and configuration audit

Read-only. Time: **12 Nov 2026, 14:51 Asia/Jakarta (WIB)**.
No application-code change. No Blueprint sync. No deploy, migrate,
cleanup, job mutation, or live storage mutation.

This report is **not** the earlier blocked heartbeat drill
(`docs/reports/PHASE_10_4B_S_STAGING_VERIFICATION.md`). That document
remains historical.

## 1. Executive summary

| Field | Value |
| --- | --- |
| Audit date | **12 Nov 2026, 14:51 Asia/Jakarta (WIB)** |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**; not independently verified) |
| Repository commit | `d10505d86cfa3ff2b04f55abe5e460ed3c6530f4` (`origin/main`) |
| Target staging API | `https://docuflow-staging-api-35ov.onrender.com` (owner-provided) |
| Overall | **BLOCKED** |

Scope: repository Blueprint and validators, targeted local tests, and
explicitly allowed public GET `/health` and `/ready` against the
owner-provided staging API hostname. Limitations: no Render dashboard
access, no staging env files, no screenshots in this workspace, no
staging DSN, no storage credentials. Owner-provided screenshots are
**OWNER-REPORTED**, not independently verified.

`DOCUFLOW_ENV=production` is the supported fail-fast mode. Source
`Settings.env` is `Literal["development", "test", "production"]`. This
audit does **not** recommend `DOCUFLOW_ENV=staging`.

Successful repository tests and GitHub CI are **not** staging
verification. Public GET 404 is infrastructure unreadiness, not
functional verification.

## 2. Repository baseline

Working tree at audit start: clean. Local branch was
`cursor/phase-10-4b-sr6-c2-post-merge-reconciliation-8f43` at
`7517a6e21d00fab4067cb405078b4fc1f12c0c81` (1 commit behind
`origin/main`). One fetch of `origin/main` confirmed:

| Field | Independent result |
| --- | --- |
| `origin/main` | `d10505d86cfa3ff2b04f55abe5e460ed3c6530f4` |
| Subject | Merge pull request #79 |
| Commit date | `2026-11-11 19:10:26 +0700` / **11 Nov 2026, 19:10 Asia/Jakarta** |
| Owner-reported deploy SHA | `d10505d` — matches `origin/main`; **not** proof of a live Render deploy |
| Main push CI | [43018051864](https://github.com/mufea/docuflow-ai/actions/runs/43018051864) **SUCCESS** (Python `130513989919`, Web `130513990270`; completed **11 Nov 2026, 19:12 Asia/Jakarta**) |

CI SUCCESS is **CI VERIFIED** for `main`. It is not **STAGING VERIFIED**.

## 3. Blueprint reconciliation

Inspected `infra/render.staging.yaml` and reused
`audit_staging_blueprint()` (zero errors).

| Requirement | Expected | Observed | Result | Evidence class |
| --- | --- | --- | --- | --- |
| API | `docuflow-staging-api` | declared, plan free | **PASS** | REPOSITORY VERIFIED |
| Web | `docuflow-staging-web` | declared, plan free | **PASS** | REPOSITORY VERIFIED |
| Database | `docuflow-staging-db` | declared, Postgres 16, plan free | **PASS** | REPOSITORY VERIFIED |
| Cleanup | `docuflow-staging-cleanup` | declared, `*/15 * * * *` | **PASS** | REPOSITORY VERIFIED |
| Broker | `inline` | API `JOB_BROKER=inline`; no `type: worker` | **PASS** | REPOSITORY VERIFIED |
| Redis | not required | no Redis service, no `REDIS_URL` | **PASS** | REPOSITORY VERIFIED |
| AI | `mock` | `AI_PROVIDER=mock` | **PASS** | REPOSITORY VERIFIED |
| Email | `console` | `EMAIL_BACKEND=console` | **PASS** | REPOSITORY VERIFIED |
| Env mode | fail-fast | `DOCUFLOW_ENV=production` on API and cleanup | **PASS** | REPOSITORY VERIFIED |
| API cleanup loop | disabled | `CLEANUP_INTERVAL_SECONDS=0` | **PASS** | REPOSITORY VERIFIED |
| DB wiring | staging DB only | `fromDatabase.name=docuflow-staging-db` | **PASS** | REPOSITORY VERIFIED |
| Production names | excluded | no `docuflow-api` / `docuflow-db` / Redis / worker | **PASS** | REPOSITORY VERIFIED |
| Git branch | `main` | not in YAML (Render dashboard setting) | **BLOCKED** live; owner-reported | OWNER-REPORTED |
| Blueprint name | `docuflowai-staging` | not in YAML | **BLOCKED** live; owner-reported | OWNER-REPORTED |
| Live sync at `d10505d` | deployed | no dashboard; HTTP 404 no-server | **NOT VERIFIED** | OWNER-REPORTED |

S3 keys remain `sync: false` (owner-supplied). Cleanup copies S3 settings
from `docuflow-staging-api`, not production service names.

## 4. Runtime configuration matrix

Live process environment was **not** readable. Rows below separate
Blueprint contract from live observation.

| Check | Expected | Observed (redacted) | Result | Evidence |
| --- | --- | --- | --- | --- |
| Environment | `DOCUFLOW_ENV=production` fail-fast | Blueprint sets it; live env unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template; live NOT VERIFIED |
| Database | dedicated `docuflow-staging-db` | Blueprint `fromDatabase`; live DSN unread | **BLOCKED** live | `/ready` unreachable; no staging DSN |
| Storage | dedicated staging bucket + keys | Blueprint `sync: false`; live unread | **BLOCKED** live | no bucket name; no object listing performed |
| AI | `mock` | Blueprint `mock`; live unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| Email | `console` | Blueprint `console`; live unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| Broker | `inline`; no paid worker | Blueprint inline, no worker | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| Cookies | `COOKIE_SECURE=true` (forced when env=production) | Blueprint `true`; live unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| CORS | staging web origin | Blueprint from `docuflow-staging-web` `RENDER_EXTERNAL_URL`; live web URL unknown | **BLOCKED** live | production hosts not in Blueprint |
| Trusted hosts | `.onrender.com` | Blueprint value present | **PASS** template | REPOSITORY VERIFIED |
| Cleanup | dedicated cron; API interval 0 | Blueprint schedule `*/15 * * * *` | **BLOCKED** live / **PASS** template | cron not triggered |
| Payments | no live Stripe/Midtrans | Blueprint does not inject payment keys | **BLOCKED** live / **PASS** template | live env unread |

`validate_staging_configuration()` was **not** executed against the
agent environment. Ambient `DATABASE_URL` is not a staging identity
(see §7). `STAGING_PREFLIGHT` was unset; preflight correctly remains
NOT EXECUTED without the flag.

## 5. Local test results

Pytest was first attempted with the ambient `DATABASE_URL`. Import of
`tests/conftest.py` loads `docuflow.main:app`, which attempted a
PostgreSQL connect to the ambient identity. DNS failed
(`Name or service not known`). No session was opened. Tests were rerun
with `DATABASE_URL=sqlite+pysqlite:///./data/phase104bs_audit.db` and
`DOCUFLOW_ENV=test` so the remote DSN was not reused.

Command:

```
DATABASE_URL='sqlite+pysqlite:///./data/phase104bs_audit.db' DOCUFLOW_ENV=test \
  uv run pytest \
  tests/test_phase98_staging.py \
  tests/test_phase99_staging.py \
  tests/test_phase910_provisioning.py \
  tests/test_phase95_readiness.py::test_ready_does_not_leak_dependency_errors \
  -q --tb=line
```

| Field | Result |
| --- | --- |
| Exit code | 0 |
| Passed | 34 |
| Failed | 0 |
| Skipped | 0 |
| Duration | 8.55s |
| Evidence | this report; command output captured **12 Nov 2026, 14:51 Asia/Jakarta** |

Coverage: Blueprint audit, production-reuse detection, DSN sanitization,
smoke-target production refusal, preflight/migrate-verify opt-in gates,
local loopback smoke `/health`+`/ready`, and `/ready` secret non-leak.

**NOT RUN:** `tests/integration/test_staging_migrate_verify.py`
(integration / migrate). `scripts/staging_preflight.py` with
`STAGING_PREFLIGHT=1` against ambient env. `scripts/staging_smoke.py`
against live staging. Provider tests.

Local tests: **PASS** / **LOCALLY VERIFIED**. Not staging runtime PASS.

## 6. Read-only runtime results

Before GET: `is_production_public_host("docuflow-staging-api-35ov.onrender.com")`
is `False` (hostname contains `staging`).
`smoke_target_errors(url, host)` is empty. Production hosts
`docuflow-api.onrender.com`, `docuflow-web.onrender.com`, and
`docuflowai.site` remain classified production and were **not** requested.

Requests: unauthenticated GET, `--max-redirs 0`, 25s timeout, no cookies.

| URL | Time (Asia/Jakarta) | HTTP | `x-render-routing` | Redirect | Body | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `https://docuflow-staging-api-35ov.onrender.com/health` | 12 Nov 2026, 14:50:57 | 404 | `no-server` | none | `Not Found` (10 bytes, text/plain) | **FAIL** |
| `https://docuflow-staging-api-35ov.onrender.com/ready` | 12 Nov 2026, 14:51:20 | 404 | `no-server` | none | `Not Found` (10 bytes, text/plain) | **FAIL** |

Elapsed ~0.10s each (Cloudflare edge). This is not a Free-plan cold start.
No JSON `status`/`checks`/`broker` body. `redis: true` was **not** observed
and would not prove a Redis server if `/ready` later returns it while
`JOB_BROKER=inline` (`health.py` sets `checks["redis"]=True` without ping
in inline mode).

Owner-provided screenshots of a live deploy at `d10505d` are
**OWNER-REPORTED** and contradicted by this GET. Historical 404s against
`docuflow-staging-api.onrender.com` were **not** re-probed (not the
confirmed origin). Staging web origin was not provided; web GET **NOT RUN**.

## 7. Credential rotation evidence

Owner-reported: new credentials for `docuflow-staging-db`.

Independent: **BLOCKED**. No Render credential list, no staging DSN, no
proof API/cleanup adopted a new credential, no proof old credentials were
revoked. A new credential existing is not adoption.

Ambient agent `DATABASE_URL` (redacted identity only; DSN not printed,
not used after the failed pytest import):

`host=dpg-dbiqe70ae00c73cdif7g-a database=docuflow_db_q32a_7751`

No `staging`/`test` isolation token. Heuristic `is_production_database`
is false without a production comparison host. **Not treated as staging.
Not treated as proven production. Not used.**

`TEST_DATABASE_URL`: `host=127.0.0.1 database=docuflow_test` (loopback).
Not used for this audit’s live checks.

## 8. Security and isolation findings

| Finding | Class |
| --- | --- |
| Staging Blueprint does not name production services, production public hosts, Redis, or a paid worker | REPOSITORY VERIFIED |
| Public GET used a staging-named hostname and did not redirect to production | INDEPENDENTLY VERIFIED |
| Live API/cleanup/database/storage isolation cannot be proven without env or a 200 `/ready` | BLOCKED |
| Ambient Render-internal DSN is not staging and must not be used for migrate/smoke | INDEPENDENTLY VERIFIED identity; connect failed |
| No screenshots present in this workspace to corroborate owner Render UI claims | NOT VERIFIED |

No production public HTTP was issued. Functional smoke that creates
application data remains **prohibited** until this gate is PASS.

## 9. Open issues

### S1 — Staging API hostname has no Render server

- Severity: **HIGH** (blocks all live staging verification)
- Evidence: HTTP 404, `x-render-routing: no-server`, ~0.10s, **12 Nov 2026, 14:50–14:51 Asia/Jakarta**
- Impact: `/health` and `/ready` FAIL; database/storage readiness NOT VERIFIED
- Owner action: confirm in the staging Render workspace that
  `docuflow-staging-api` exists and that
  `docuflow-staging-api-35ov.onrender.com` is attached
- Separate authorization: **yes** for any provision, sync, or deploy

### S2 — Live runtime configuration unread

- Severity: **HIGH**
- Evidence: `STAGING_*` unset; no dashboard; Blueprint is template only
- Impact: D1–D9 live rows BLOCKED
- Owner action: redacted env screenshots (keys and non-secret values only) or an owner-run `STAGING_PREFLIGHT=1` on a staging-only machine
- Separate authorization: **yes** before any agent-held staging secrets

### S3 — Live database isolation unproven

- Severity: **HIGH**
- Evidence: no staging DSN; `/ready` 404
- Impact: cannot prove API/cleanup use `docuflow-staging-db`
- Owner action: after S1 is live, owner-run identity check (`database_identity` / `STAGING_DATABASE_CONFIRM`) without pasting the DSN
- Separate authorization: **yes** for any SQL or migrate-verify that connects

### S4 — Live storage isolation unproven

- Severity: **HIGH**
- Evidence: bucket name not in repo (`sync: false`); no object listing performed
- Impact: cannot prove a dedicated staging bucket
- Owner action: screenshot of `S3_BUCKET` **name only**
- Separate authorization: **yes** before any object operation

### S5 — Credential rotation unproven

- Severity: **MEDIUM**
- Evidence: owner-reported only
- Impact: old DB credentials may still be valid
- Owner action: confirm API/cleanup connection strings match the new credential; revoke unused credentials
- Separate authorization: **yes** for rotate/revoke

### S6 — Ambient agent DSN is not staging

- Severity: **HIGH** (misuse risk)
- Evidence: redacted identity in §7
- Impact: preflight/migrate/smoke against this DSN could touch a non-staging database
- Owner action: do not point agent `DATABASE_URL` at staging or production; keep staging DSNs off this workspace
- Separate authorization: **yes** before any connect

## 10. Final gate decision

**BLOCKED** — Evidence insufficient; complete prerequisites before
functional smoke testing.

Rationale: Blueprint and local validators **PASS**. Independently
verified public GET against the owner-provided staging API is HTTP 404
`no-server`. Live configuration, database isolation, storage isolation,
credential adoption, cleanup execution, and deploy identity are not
independently verified. Functional smoke is **prohibited**.

Not **FAIL** for production-safety violation: the probed hostname is
staging-classified and did not redirect to production. Not **PASS**:
isolation of live resources is unproven and the API is not serving.

## 11. Next safe actions

1. Owner confirms Render workspace and that
   `docuflow-staging-api-35ov.onrender.com` is the live API (S1).
2. If no-server persists, separately authorize Blueprint apply/sync or
   deploy. Do not infer that authorization from this audit or from the
   owner name.
3. After unauthenticated GET `/health` and `/ready` return HTTP 200 with
   `database`/`storage` true and `broker=inline`, record that evidence.
4. Owner supplies redacted proof of staging DB identity, bucket **name**,
   `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`, and no payment keys (S2–S4).
5. Only then request a **separate** authorization for mutating functional
   smoke (`STAGING_SMOKE_MUTATIONS=1` is still not granted).

No speculative infrastructure changes. No Redis. No paid worker.
)
