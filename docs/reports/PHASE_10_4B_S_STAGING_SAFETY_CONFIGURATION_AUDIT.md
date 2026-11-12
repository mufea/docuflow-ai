# Phase 10.4B-S — Staging safety and configuration audit

Read-only. First pass: **12 Nov 2026, 14:51 Asia/Jakarta (WIB)**.
Reprobe: **12 Nov 2026, 15:09 Asia/Jakarta (WIB)**.
No application-code change. No Blueprint sync. No deploy, migrate,
cleanup, job mutation, or live storage mutation.

This report is **not** the earlier blocked heartbeat drill
(`docs/reports/PHASE_10_4B_S_STAGING_VERIFICATION.md`). That document
remains historical.

## 1. Executive summary

| Field | Value |
| --- | --- |
| Audit date | **12 Nov 2026, 15:09 Asia/Jakarta (WIB)** (reprobe) |
| First pass | **12 Nov 2026, 14:51 Asia/Jakarta (WIB)** |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**; not independently verified) |
| Repository commit | `d9ee5f84e7aae8bfadfcf55940df81d7f0072bd0` (`origin/main`) |
| Target staging API | `https://docuflow-staging-api-350v.onrender.com` (owner-provided) |
| Prior hostname | `https://docuflow-staging-api-35ov.onrender.com` (letter `o`; 404 no-server) |
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
verification. HTTP 200 `/health` and `/ready` are infrastructure
readiness only. They do **not** prove production isolation or functional
verification.

## 2. Repository baseline

Reprobe working tree: clean. Local branch was
`cursor/phase-10-4b-s-staging-safety-audit-8f43` at
`719a64181c1dcf92e9c3bb0e503ef4926452cc0c` (1 commit behind
`origin/main`). One fetch of `origin/main` confirmed:

| Field | Independent result |
| --- | --- |
| `origin/main` | `d9ee5f84e7aae8bfadfcf55940df81d7f0072bd0` |
| Subject | Merge pull request #80 |
| Commit date | `2026-11-12 15:02:32 +0700` / **12 Nov 2026, 15:02 Asia/Jakarta** |
| PR #80 CI | [43178570667](https://github.com/mufea/docuflow-ai/actions/runs/43178570667) **SUCCESS** |
| Main push CI | [43179741838](https://github.com/mufea/docuflow-ai/actions/runs/43179741838) **SUCCESS** (Python `131052542505`, Web `131052542881`; completed **12 Nov 2026, 15:04 Asia/Jakarta**) |
| `src/` / `infra/` vs first-pass SHA `d10505d` | unchanged (docs-only merge) |
| Owner-reported deploy SHA | `d10505d` — still **not** proven as the live Render process SHA |

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
| Live sync at `d10505d` | deployed | API serves `/health`+`/ready` on `350v`; process SHA unread | **NOT VERIFIED** SHA / **PASS** HTTP | OWNER-REPORTED SHA; INDEPENDENTLY VERIFIED HTTP |

S3 keys remain `sync: false` (owner-supplied). Cleanup copies S3 settings
from `docuflow-staging-api`, not production service names.

## 4. Runtime configuration matrix

Live process environment was **not** readable. Rows below separate
Blueprint contract from live observation.

| Check | Expected | Observed (redacted) | Result | Evidence |
| --- | --- | --- | --- | --- |
| Environment | `DOCUFLOW_ENV=production` fail-fast | Blueprint sets it; live env unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template; live NOT VERIFIED |
| Database | dedicated `docuflow-staging-db` | Blueprint `fromDatabase`; `/ready` `database=true`; live DSN unread | **BLOCKED** isolation / **PASS** reachability | HTTP 200 does not prove staging vs production DB |
| Storage | dedicated staging bucket + keys | Blueprint `sync: false`; `/ready` `storage=true`; live unread | **BLOCKED** isolation / **PASS** ping | no bucket name; no object listing performed |
| AI | `mock` | Blueprint `mock`; live unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| Email | `console` | Blueprint `console`; live unread | **BLOCKED** live / **PASS** template | REPOSITORY VERIFIED template |
| Broker | `inline`; no paid worker | `/ready` `broker=inline`, `rq_workers=0` | **PASS** live JSON | INDEPENDENTLY VERIFIED; `redis:true` is inline no-ping |
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

Local tests: **PASS** / **LOCALLY VERIFIED** (first pass). Reprobe did
**not** re-run them: `src/` and `infra/` are unchanged vs `d10505d`.
Not staging runtime PASS.

## 6. Read-only runtime results

Production hosts `docuflow-api.onrender.com`, `docuflow-web.onrender.com`,
and `docuflowai.site` remain classified production and were **not**
requested. Requests: unauthenticated GET, `--max-redirs 0`, no cookies.

Hostname discrepancy: first-pass origin used letter `o` (`35ov`).
Reprobe origin uses digit `0` (`350v`). They are different hosts.
`is_production_public_host` is `False` for both (substring `staging`).

### 6.1 First pass — `35ov` (letter o)

| URL | Time (Asia/Jakarta) | HTTP | `x-render-routing` | Redirect | Body | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `https://docuflow-staging-api-35ov.onrender.com/health` | 12 Nov 2026, 14:50:57 | 404 | `no-server` | none | `Not Found` | **FAIL** |
| `https://docuflow-staging-api-35ov.onrender.com/ready` | 12 Nov 2026, 14:51:20 | 404 | `no-server` | none | `Not Found` | **FAIL** |

### 6.2 Reprobe — `350v` (digit 0) — current confirmed origin

Before GET: `smoke_target_errors(url, host)` is empty.

| URL | Time (Asia/Jakarta) | HTTP | Redirect | Body (redacted) | Result |
| --- | --- | --- | --- | --- | --- |
| `https://docuflow-staging-api-350v.onrender.com/health` | 12 Nov 2026, 15:09:41 | 200 | none | `{"status":"ok","service":"docuflow-api"}` | **PASS** |
| `https://docuflow-staging-api-350v.onrender.com/ready` | 12 Nov 2026, 15:09:50 | 200 | none | `status=ready`, `checks.database=true`, `checks.storage=true`, `checks.redis=true`, `broker=inline`, `rq_workers=0` | **PASS** |

Elapsed 0.10s (`/health`) and 0.64s (`/ready`). No secret fragments.
`checks.redis=true` with `broker=inline` is set without a Redis ping in
`src/docuflow/api/routes/health.py`. It does **not** prove a Redis
server exists or is required.

Owner-reported deploy SHA `d10505d` remains **OWNER-REPORTED**. HTTP
does not expose the running git SHA. Staging web origin was not
provided; web GET **NOT RUN**.

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
| Public GET used staging-named hostnames and did not redirect to production | INDEPENDENTLY VERIFIED |
| Live `/ready` proves a DB and storage ping succeed; not which database or bucket | INDEPENDENTLY VERIFIED reachability; isolation BLOCKED |
| Ambient Render-internal DSN is not staging and must not be used for migrate/smoke | INDEPENDENTLY VERIFIED identity; connect failed |
| No screenshots present in this workspace to corroborate owner Render UI claims | NOT VERIFIED |

No production public HTTP was issued. Functional smoke that creates
application data remains **prohibited** until this gate is PASS.

## 9. Open issues

### S1 — Wrong hostname `35ov` had no Render server — **CLOSED** for confirmed `350v`

- Severity: **HIGH** on first pass; **CLOSED** on reprobe for `350v`
- Evidence: `35ov` HTTP 404 `no-server` at 14:50–14:51; `350v` HTTP 200
  `/health` and `/ready` at **12 Nov 2026, 15:09 Asia/Jakarta**
- Impact: first-pass FAIL was a hostname transcription (`o` vs `0`), not
  a missing stack
- Owner action: use `docuflow-staging-api-350v.onrender.com` as the API
  origin; do not treat `35ov` as live
- Separate authorization: not required for further public GET `/health`
  `/ready` on `350v`

### S2 — Live runtime configuration unread

- Severity: **HIGH**
- Evidence: `STAGING_*` unset; no dashboard; Blueprint is template only
- Impact: D1–D9 live rows BLOCKED
- Owner action: redacted env screenshots (keys and non-secret values only) or an owner-run `STAGING_PREFLIGHT=1` on a staging-only machine
- Separate authorization: **yes** before any agent-held staging secrets

### S3 — Live database isolation unproven

- Severity: **HIGH**
- Evidence: `/ready` `database=true` on `350v`; live DSN unread; no
  `STAGING_DATABASE_CONFIRM`
- Impact: cannot prove the reachable DB is `docuflow-staging-db` rather
  than another Postgres
- Owner action: owner-run identity check (`database_identity` /
  `STAGING_DATABASE_CONFIRM`) without pasting the DSN
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
verified GET against `docuflow-staging-api-350v.onrender.com` is HTTP
200 `/health` (`status=ok`) and HTTP 200 `/ready` (`status=ready`,
`database=true`, `storage=true`, `broker=inline`, `rq_workers=0`).
That is infrastructure readiness, not isolation. Live env values,
database identity, storage bucket name, credential adoption, cleanup
execution, and deploy SHA are not independently verified. Functional
smoke is **prohibited**.

Not **FAIL** for production-safety violation: both probed hostnames are
staging-classified and did not redirect to production. Not **PASS**:
isolation of live resources is unproven.

## 11. Next safe actions

1. Keep using `https://docuflow-staging-api-350v.onrender.com` as the
   API origin. Do not use `35ov`.
2. Owner supplies redacted proof of staging DB identity, bucket
   **name**, `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`, and no payment
   keys (S2–S5). Do not paste DSNs or secrets into chat.
3. Only then request a **separate** authorization for mutating
   functional smoke (`STAGING_SMOKE_MUTATIONS=1` is still not granted).

No speculative infrastructure changes. No Redis. No paid worker.
)
