# Phase 10.4B-SR6-A — Staging infrastructure audit and remediation plan

Part 1, audit-only. Time: **11 Nov 2026, 16:54 Asia/Jakarta (WIB)**.
No provision, deploy, migrate, env change, or job mutation.
Owner approval for Part 2: **NOT REQUESTED**.

## 1. Executive summary

PR #73 is **MERGED**. Main CI is **SUCCESS**. SR5 status is corrected to
**MERGED**. Documented staging hosts remain unreachable. Minimum path
to 10.4B-S is reuse of existing `infra/render.staging.yaml` (inline,
no Redis, no paid worker). Do not execute those actions in this part.

## 2. Repository baseline

| Field | Owner-reported | Independent |
| --- | --- | --- |
| PR | #73 | [#73](https://github.com/mufea/docuflow-ai/pull/73) **MERGED**, base `main` |
| Merge SHA | `c081dc844075b6d76e7938de3cdc401837676f03` | `origin/main` HEAD; merge `2026-11-11T09:45:00Z` / **16:44 Asia/Jakarta** |
| PR head | — | `e02190294d15a7def8b5ec0c5231829840641242` |
| Main CI | `42997784272` SUCCESS | same run `conclusion=success`, completed `2026-11-11T09:46:51Z` / **16:46 Asia/Jakarta** |
| Python | `130446084354` | SUCCESS |
| Web | `130446084891` | SUCCESS |

No later `main` push. Render dashboard inventory: **UNKNOWN**.
Phase 10.4B implementation remains **MERGED** (PR #65).

SR5 on `c081dc8` still showed **COMPLETE – UNMERGED**. This phase
records **MERGED**. Staging/production labels unchanged.

## 3. SR5 blocker review

Source: `docs/reports/PHASE_10_4B_SR5_BLOCKER_CLOSURE_PLAN.md`
(**HISTORICAL** text). Live HTTP rechecked **16:54 Asia/Jakarta**.

| ID | Component | Severity | Evidence | Class | State | Required action | Dependency | Verification | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | Workspace | HIGH | dashboard unavailable | **UNKNOWN** | UNKNOWN | List `docuflow-staging-*`; stop if production names | none | Written inventory | Owner |
| B1 | API/Web/DB/cron | CRITICAL | 404 no-server at 16:54 | **VERIFIED** | **BLOCKED** | Apply only `infra/render.staging.yaml` if missing | B0 | `/health` 200; `/ready` database+storage | Owner |
| B3 | Deploy SHA | HIGH | service absent | **VERIFIED** | **BLOCKED** | Deploy `17dfe9c` or later (`c081dc8`) | B1 | Render SHA recorded | Owner |
| B2 | Test isolation | CRITICAL | `STAGING_*` UNSET | **VERIFIED** | **BLOCKED** | Local operator env | B1 | URL matches live API | Owner |
| B4 | DB process | HIGH | agent DSN not staging; unused | **VERIFIED** | **BLOCKED** | Render Shell SQL only | B1 | Agent DSN never opened | Owner |
| B5 | Worker | MEDIUM | Blueprint inline | **VERIFIED** (repo) | **ACCEPTED** | SQL backdate; no API restart | none | S2 process-kill stays NOT VERIFIED | Owner |

Suspected only: H1–H3, H6, H7. Rejected: H4, H5.

## 4. Infrastructure inventory

| Resource | Repo Blueprint | Live | Classification |
| --- | --- | --- | --- |
| `docuflow-staging-api` | defined, Free web, `JOB_BROKER=inline` | 404 no-server | **CONFIGURED** (repo) / **BLOCKED** (live) |
| `docuflow-staging-web` | defined, Free web | 404 no-server | same |
| `docuflow-staging-db` | Free Postgres 16 | unreachable | same |
| `docuflow-staging-cleanup` | cron `*/15` `python -m docuflow.cleanup` | unreachable | same |
| Redis | omitted while inline | n/a | **NOT REQUIRED** |
| Paid worker | omitted | n/a | **NOT REQUIRED** |
| Staging S3 | `S3_*` `sync: false` | `/ready` unreachable | **BLOCKED** |
| Heartbeat env | app default 60s; not pinned in Blueprint | **UNKNOWN** | **CONFIGURED** (repo) |
| `JOB_STALE_MINUTES` | Blueprint `90` | **UNKNOWN** | **CONFIGURED** (repo) |

Blueprint file is a template. It is **not** proof that staging exists.

## 5. Architecture

Designed staging and default production: **inline** jobs in the API
(`WORKER_CONCURRENCY=2`). Recovery is **fail+refund via cleanup**, not
a second worker reclaiming `processing`. Fencing is `status=processing`
on heartbeat UPDATE and stale fail. Credits: `reserve:` / `settle:` /
`refund:` + `{job_id}`. Heartbeat: `JOB_HEARTBEAT_SECONDS` default 60
(`src/docuflow/config.py`). Inline is **not** RQ-worker evidence.

## 6. Test prerequisites (10.4B-S, not executed)

S1 heartbeat, S3–S7 stale/fencing/recovery, S8 retry, S9–S10 credits,
S11 results, S12 audit: need live API+DB+storage+cleanup+isolated user.
S2 process-kill: **NOT REQUIRED** to close fail+refund; remains NOT
VERIFIED on shared Free API. PostgreSQL is required. Redis/separate
worker **NOT REQUIRED**. Tests must use isolated smoke user, Render
Shell SQL on **one** test job, never agent `DATABASE_URL`.

## 7. Minimum remediation (not executed)

Reuse existing Blueprint. Do **not** add Redis or a worker.

| # | Blocker | Resource | Why | Reuse? | Proposed change | Cost | Risk | Security | Rollback | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | B0 | Render staging workspace | Avoid production collision | existing workspace if 9.10D still exists | inspect only | **UNKNOWN** (time) | HIGH if wrong workspace | production names | no mutation | inventory list |
| A1 | B1 | `docuflow-staging-*` | no-server | yes, `infra/render.staging.yaml` | apply Blueprint **only if missing** | **UNKNOWN** (Free hours + Postgres 30-day window + cron seconds + external S3) | HIGH if applied to production workspace | staging bucket only | delete only staging resources just created | `/health` `/ready` |
| A2 | B3 | API + cleanup | heartbeat code | existing git `main` | deploy `c081dc8` or later | **UNKNOWN** (deploy minutes) | MEDIUM (boot migrate) | no prod DSN | Redeploy previous SHA | Render SHA ≥ `17dfe9c` |
| A3 | B1 proof | public HTTP | current verification | existing hosts | GET `/health` `/ready` | none | LOW | no secrets in body | n/a | 200 + database/storage true |
| A4 | B2 | operator env | isolation | n/a | set `STAGING_*` locally | none | HIGH if prod creds | never paste to chat | unset local vars | host confirm match |
| A5 | B4 | process | wrong DSN | n/a | Shell SQL only | none | CRITICAL if agent DSN used | no DSN print | n/a | unused agent DSN |

Optional later (not required): pin `JOB_HEARTBEAT_SECONDS=60` in
Blueprint. Application-code change: **not required**.

## 8. Cost and risk

Cost figures: **UNKNOWN**. Blueprint comments: Free web spin-down, 750
instance hours/workspace/month; Free Postgres 1 GB, one per workspace,
expires ~30 days after creation (9.10D was 7 Nov 2026); cron billed
for run seconds; S3 billed by provider. Confirm live Render price list
before Part 2.

Highest risk: applying Blueprint in a workspace that already has
`docuflow-api` / `docuflow-db`. Stop at A0 if that is true.

## 9. Rollback

- A0: none (read-only).
- A1: remove only newly created `docuflow-staging-*`. Never delete
  production.
- A2: redeploy prior SHA.
- A4: unset local env.
- Do not apply `infra/render.yaml` as rollback.

## 10. Owner approval checklist (Part 2 — do not execute)

Approve **separately**. Default: deny.

| ID | Resource | Env | Exact change | Cost | Risk | Rollback | Verify |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | workspace list | staging Render | inspect names only | UNKNOWN | HIGH if mis-identified | none | no production names |
| A1 | Blueprint apply | staging only | `infra/render.staging.yaml` if missing | UNKNOWN | HIGH | delete new staging resources | services exist |
| A2 | git deploy | staging API/cron | `c081dc8` or later | UNKNOWN | MEDIUM | prior SHA | deploy SHA |
| A3 | HTTP GET | public staging | `/health` `/ready` | none | LOW | n/a | 200 + ready flags |
| A4 | local env | operator machine | `STAGING_*` | none | HIGH if prod | unset | host match |
| A5 | process | operator | no agent DSN | none | CRITICAL if skipped | n/a | Shell only |

A1–A2 require explicit owner authorization. This part does not request
it.

## 11. 10.4B-S readiness — **BLOCKED**

Mandatory current **VERIFIED**: live API/web, staging Postgres,
10.4B schema, inline topology (Redis not required), cleanup available,
heartbeat interval known, isolated credentials, no production, owner
mutation authorization. All unmet or UNKNOWN except designed topology
in repo.

## 12. Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Full tests | **not run** |
| Infrastructure mutation | **not run** |
