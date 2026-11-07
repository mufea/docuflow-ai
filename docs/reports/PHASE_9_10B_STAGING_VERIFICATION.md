# Phase 9.10B — Staging functional verification

This report records a **read-first audit**, a **safety preflight**, and a
**non-mutating baseline** against Render staging. Mutating lifecycle tests
were **not executed**.

Status vocabulary (never combined):

| Label | Meaning |
| --- | --- |
| PASS | Check ran and succeeded |
| FAIL | Check ran and failed |
| SKIPPED | Check was not run because a required opt-in or credential was absent |
| NOT EXECUTED | Required live step was not attempted |
| BLOCKED | Required owner authorization or credentials are missing |
| Owner-reported | Owner statement; not independently re-checked here |
| Locally tested | Executed in this Cloud Agent environment |

## A. Environment

| Item | Value |
| --- | --- |
| Repository URL | https://github.com/mufea/docuflow-ai |
| Inspected default branch | `origin/main` `b15115889d88919e8b5ac1c1cc29ed8a6e8d31c3` (PR #15 merge). Not switched. |
| Working branch | `cursor/phase-9-10b-staging-functional-8f43` (from Phase 9.10A evidence `a2a61ee`) |
| Previous evidence | Phase 9.10A, [PR #16](https://github.com/mufea/docuflow-ai/pull/16) (open at report time) |
| Staging API URL | `https://docuflow-staging-api.onrender.com` |
| Staging frontend URL | `https://docuflow-staging-web.onrender.com` |
| Test execution timestamp | 7 Nov 2026, 08:20 Asia/Jakarta (WIB) |
| Broker mode | `inline` (`GET /ready`) |
| Database readiness | `/ready` `checks.database=true` |
| Storage readiness | `/ready` `checks.storage=true` |
| Redis / worker | Owner-reported absent. `/ready` `broker=inline`. Absent Redis is expected. |

No credentials, DSNs, tokens, or signed URLs are recorded here.

## B. Repository audit (Phase A)

Existing smoke: `scripts/staging_smoke.py`. Session cookies (`POST /v1/auth/login`),
not bearer tokens. CSRF via `df_csrf` + `X-CSRF-Token` + `Origin`. Jobs use
`JOB_BROKER=inline` (`POST /v1/jobs` then `GET /v1/jobs/{id}`). Staging download
returns HTTP 302 to a signed URL; the smoke client does not follow redirects.
`TEST_S3_*` is the provider-test path and is **not** interchangeable with live
staging `S3_*` on Render.

| Area | Existing implementation | Verification requirement | Risk |
| --- | --- | --- | --- |
| Isolation | `smoke_target_errors` + `STAGING_HOST_CONFIRM`; production hosts refused | Confirm hostname is `docuflow-staging-api.onrender.com` | LOW — hostname matches; production hosts rejected |
| Mutation gate | `STAGING_SMOKE_MUTATIONS` must equal `1` (`true` is FAIL) | Owner sets the flag in the execution environment | **BLOCKER** — unset in this environment |
| Auth credentials | `STAGING_SMOKE_EMAIL` / `STAGING_SMOKE_PASSWORD` | Dedicated staging account, not production/admin unless approved | **BLOCKER** — unset; values must not be pasted in chat |
| Registration | Second opt-in `STAGING_SMOKE_REGISTER=1` | Do not auto-create accounts | LOW if login-only; HIGH if register is enabled without a dedicated mailbox |
| Upload | `POST /v1/documents` multipart PDF from `STAGING_SMOKE_PDF` | Harmless unique test PDF | **BLOCKER** — path unset; no PDF fixture in the repo |
| Job processing | `POST /v1/jobs` `extract_text`; poll until terminal | Inline broker; no worker | MEDIUM — Free spin-down can kill in-flight inline jobs |
| Download | `GET /v1/documents/{id}/download` accepts 200 or 302 | HTTP status only; signed URL not logged | MEDIUM — content checksum is **not** in the existing smoke |
| Unauthenticated access | `GET /v1/auth/me` requires session | 9.10B asked for unauthenticated rejection | LOW gap — existing smoke does not call `/me` without cookies |
| Delete | `DELETE /v1/documents/{id}`; best-effort delete on failure | Only the smoke-created document | MEDIUM — object-store absence is not independently checked |
| Cross-user | Optional second account | Isolation of the uploaded document | SKIPPED unless second account is provided |
| Cleanup cron | Render cron `*/15 * * * *`; API `CLEANUP_INTERVAL_SECONDS=0` | Cron run not part of HTTP smoke | Not in this phase |
| Hosted migrate-verify | `scripts/staging_migrate_verify.py` | Separate workstream; `ipAllowList: []` | Out of scope; **not claimed** |
| Provider tests | `pytest -m provider` + `TEST_S3_*` | Dedicated test bucket, not staging Render `S3_*` | Do not reuse |

Exact commands (mutating block is owner-only; do not set the gate from chat):

```bash
# Non-mutating baseline (executed 7 Nov 2026, 08:20 Asia/Jakarta)
STAGING_API_URL=https://docuflow-staging-api.onrender.com \
STAGING_HOST_CONFIRM=docuflow-staging-api.onrender.com \
STAGING_WEB_URL=https://docuflow-staging-web.onrender.com \
STAGING_SMOKE_TIMEOUT=90 \
uv run python scripts/staging_smoke.py
```

```bash
# Mutating lifecycle — owner execution environment only.
# Do not paste passwords into chat. Do not commit these values.
export STAGING_API_URL=https://docuflow-staging-api.onrender.com
export STAGING_HOST_CONFIRM=docuflow-staging-api.onrender.com
export STAGING_WEB_URL=https://docuflow-staging-web.onrender.com
export STAGING_SMOKE_MUTATIONS=1
export STAGING_SMOKE_EMAIL=...          # dedicated staging test user
export STAGING_SMOKE_PASSWORD=...       # not production
export STAGING_SMOKE_PDF=./path/to/tiny-test.pdf
# Optional: STAGING_SMOKE_REGISTER=1 only if a new dedicated staging user must be created.
# Optional: STAGING_SMOKE_SECOND_EMAIL / STAGING_SMOKE_SECOND_PASSWORD for cross-user 403.
uv run python scripts/staging_smoke.py
```

No mutating operations were executed during the audit.

## C. Safety preflight (Phase B)

| Check | Result |
| --- | --- |
| API URL is staging hostname | PASS — `docuflow-staging-api.onrender.com` (contains isolation token; not `docuflow-api`) |
| Frontend URL is staging | PASS — `docuflow-staging-web.onrender.com` |
| `STAGING_SMOKE_MUTATIONS=1` | **FAIL / absent** — UNSET. Agent did not set it. |
| Staging auth credentials present | **UNSET** (`STAGING_SMOKE_EMAIL`, `STAGING_SMOKE_PASSWORD`) |
| Dedicated staging account | **NOT VERIFIED** — no account in this environment |
| Account is not production/admin | **NOT VERIFIED** |
| Storage is staging | Owner-reported staging bucket. `/ready` storage true. Render `S3_*` not in this environment. |
| Database is staging | Owner-reported `docuflow_staging_db`. `/ready` database true. `DATABASE_URL` UNSET here. |
| Production DSN / production S3 in this env | PASS — `DATABASE_URL` and `S3_*` UNSET; smoke used only the staging origin |
| `TEST_S3_*` unused for this run | PASS — UNSET; not used |
| Cleanup strategy understood | Yes — smoke deletes only the document it uploaded; cron is separate |
| Unique test data | Not created — mutations did not run |
| Production API contacted | No |

Mandatory safety gate: mutating smoke stayed disabled.

**MUTATING STAGING SMOKE: NOT AUTHORIZED**

## D. Non-mutating baseline (Phase C)

Re-ran the existing script with mutations **not** enabled (7 Nov 2026, 08:20 Asia/Jakarta). Bounded timeout 90s. Exit 0.

| Test | Result | Evidence |
| --- | --- | --- |
| `GET /health` | PASS | HTTP 200 `status=ok` `service=docuflow-api` |
| `GET /ready` | PASS | HTTP 200 `broker=inline` `checks={'database': True, 'redis': True, 'storage': True}` |
| Frontend | PASS | HTTP 200 |
| Staging database readiness | PASS | `/ready` `database=true` (connectivity, not migrate-verify) |
| Staging storage readiness | PASS | `/ready` `storage=true` |

`checks.redis=true` with no Redis service is existing inline-broker ready behavior, not a Redis deployment.

## E. Functional test results (Phase D)

Mutations were not started. No documents, jobs, or users were created by this run.

| Test | Result | Evidence |
| --- | --- | --- |
| Authentication | SKIPPED | `STAGING_SMOKE_MUTATIONS` is not `1`; credentials UNSET |
| Protected endpoint | SKIPPED | `/v1/auth/me` not called |
| Unauthenticated rejection | SKIPPED | Not in this run |
| Upload | SKIPPED | Gate + `STAGING_SMOKE_PDF` UNSET |
| Job creation | SKIPPED | Gate absent |
| Job processing | SKIPPED | Gate absent |
| Download | SKIPPED | Gate absent |
| Content integrity | SKIPPED | Existing smoke does not checksum bodies; not run |
| Delete | SKIPPED | Gate absent |
| Cleanup | SKIPPED | No smoke document created; cron not independently verified |
| Cross-user access | SKIPPED | Gate absent |

No FAIL rows. No leftover smoke documents from this agent.

## F. Safety verification

| Item | Status |
| --- | --- |
| Staging isolation verified | Yes for HTTP origin (hostname + confirm). |
| Dedicated account verified | No — credentials absent. |
| Mutation authorization verified | **No** — `STAGING_SMOKE_MUTATIONS` UNSET. |
| No production access performed | Yes. |
| No production resources modified | Yes. |
| No credentials exposed | Yes — names inspected, values never printed. |
| Application code changed | No. |
| Hosted migration verification | **Not verified** (separate workstream). |

## G. Remaining limitations

| Claim | Classification |
| --- | --- |
| Staging services exist | Owner-reported (9.10A) plus `/health` `/ready` frontend PASS |
| Provider connectivity | Owner-reported `pytest -m provider` PASS (6 Nov 2026) |
| Non-mutating HTTP baseline | Locally tested PASS (this report) |
| Authentication / upload / job / download / delete | Skipped |
| Content integrity checksum | Not verified by existing smoke even after a future mutating PASS |
| Unauthenticated `/v1/auth/me` | Not in existing smoke |
| Object-store object gone after delete | Not independently verified by existing smoke |
| Hosted `staging_migrate_verify.py` | Not verified |
| Production | Not deployed, not authorized |

Existing smoke is sufficient to start the mutating lifecycle once the owner
enables the gate and injects credentials **outside chat**. No application-code
change is proposed. A later smoke improvement (unauthenticated 401 + download
checksum without logging signed URLs) is optional and was **not** made here.

## H. Git

Documentation-only commit on `cursor/phase-9-10b-staging-functional-8f43`.
No `.env`, no PDFs, no secrets.

## I. Final status

| Status | Value |
| --- | --- |
| STAGING PROVISIONED | YES |
| PROVIDER VERIFIED | YES (owner-run provider test) |
| STAGING FUNCTIONAL VERIFIED | **NO** |
| STAGING VERIFIED | **NO** |
| PRODUCTION DEPLOYED | **NO** |
| PRODUCTION AUTHORIZED | **NO** |

**MUTATING STAGING SMOKE: NOT AUTHORIZED**
