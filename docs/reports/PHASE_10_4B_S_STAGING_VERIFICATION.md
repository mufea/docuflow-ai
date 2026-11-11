# Phase 10.4B-S — Controlled staging verification

Stopped after Gate C. Time: **11 Nov 2026, 15:43 Asia/Jakarta (WIB)**.
No application-code change. No staging mutation. No production access.

## 1. Objective

Execute the Phase 10.4B-S heartbeat and stale-recovery drill on staging.
Execution **did not start**. Staging HTTP endpoints that were live in
Phase 9.10D are not serving.

## 2. Gate A — Main CI

Verified before any staging probe beyond public GET.

| Field | Value |
| --- | --- |
| `origin/main` | `0c97790ac5464bb674494ca83679a4bc6ca9c1d8` |
| PR #67 | [#67](https://github.com/mufea/docuflow-ai/pull/67) **MERGED** |
| Merged at | `2026-11-11T08:42:01Z` / **11 Nov 2026, 15:42 Asia/Jakarta** |
| PR head | `a056ce4af6e75adcb09aab4aeffcc9b7f80f4c34` |
| PR CI | [42988801228](https://github.com/mufea/docuflow-ai/actions/runs/42988801228) **SUCCESS** |
| Main push CI | [42989107356](https://github.com/mufea/docuflow-ai/actions/runs/42989107356) **SUCCESS** |
| Main CI completed | `2026-11-11T08:43:56Z` / **11 Nov 2026, 15:43 Asia/Jakarta** |
| Main Python | `130417329445` SUCCESS |
| Main Web | `130417329978` SUCCESS |

Intervening commits: none after `0c97790`. PR CI SUCCESS was not used as
a substitute for main push CI.

## 3. Gate B — Documentation

On `origin/main` before this report:

- Phase 10.4B implementation: **MERGED** (PR #65)
- Phase 10.4B-R2: **MERGED** (PR #66)
- Phase 10.4B-R3: **COMPLETE – UNMERGED** (stale after PR #67)

This document and `docs/IMPLEMENTATION_STATUS.md` mark 10.4B-R3
**MERGED** with the Gate A workflow IDs. Phase 9.15 / backup / DR labels
are unchanged.

## 4. Gate C — Staging infrastructure

Non-mutating public GET only. No login, upload, job, SQL, or deploy.

| Target | Result | Time |
| --- | --- | --- |
| `https://docuflow-staging-api.onrender.com/health` | HTTP 404, `x-render-routing: no-server` | 11 Nov 2026, 15:43 Asia/Jakarta |
| `https://docuflow-staging-api.onrender.com/ready` | HTTP 404, `x-render-routing: no-server` | same |
| `https://docuflow-staging-web.onrender.com/` | HTTP 404, `x-render-routing: no-server` | same |

`x-render-routing: no-server` means Render has no process for that
hostname. This is not a cold-start delay (response ~0.1s).

Agent environment:

| Name | Presence | Used? |
| --- | --- | --- |
| `STAGING_API_URL` | UNSET | no |
| `STAGING_WEB_URL` | UNSET | no |
| `STAGING_HOST_CONFIRM` | UNSET | no |
| `STAGING_SMOKE_MUTATIONS` | UNSET | no |
| `STAGING_SMOKE_EMAIL` / password | UNSET | no |
| `DATABASE_URL` | SET | **no** — database name is not `docuflow_staging_db`; DSN not opened |
| `TEST_DATABASE_URL` | SET | **no** — loopback `docuflow_test` only |

The agent `DATABASE_URL` host is a Render private hostname. The database
name does not contain `staging` and does not match the 9.10D staging
name `docuflow_staging_db`. It was not used.

| Item | Classification | Notes |
| --- | --- | --- |
| Staging API HTTP | **MISSING** | 404 no-server |
| Staging web HTTP | **MISSING** | 404 no-server |
| Staging PostgreSQL | **MISSING** | no API `/ready`; no staging DSN in this environment |
| Separate worker | **NOT APPLICABLE** | architecture is `JOB_BROKER=inline` |
| Broker | **CONFIGURED BUT NOT VERIFIED** | Blueprint inline; live env not readable |
| Storage | **MISSING** | `/ready` unreachable |
| Heartbeat env | **CONFIGURED BUT NOT VERIFIED** | default 60 in code; Blueprint does not pin it |
| Stale threshold | **CONFIGURED BUT NOT VERIFIED** | Blueprint 90; live env not readable |
| Cleanup cron | **MISSING** | no-server; cron not independently probed |
| 10.4B deploy SHA | **MISSING** | cannot inspect a missing service |
| Isolated test account | **MISSING** | smoke credentials unset |
| Migration head on staging | **NOT VERIFIED** | 9.10D was Alembic `0003`; not rechecked |

**Staging readiness: BLOCKED.**

Inline jobs are the documented staging/production-default architecture.
A separate RQ worker is not required for 10.4B fail+refund recovery.
Scenario 2 still cannot terminate a “test worker” without restarting the
shared API, which this phase forbids. That remains a constraint after
staging is restored.

## 5. Safety decisions

| Check | Result |
| --- | --- |
| Environment is staging | **FAIL** — documented staging hosts have no server |
| Staging PostgreSQL confirmed | **FAIL** — not reachable; agent DSN is not the 9.10D staging name |
| Isolated test accounts | **FAIL** — credentials unset |
| No production DSN used | **PASS** — no database connection opened |
| Safe cleanup | **NOT APPLICABLE** — no test data created |
| Cannot affect customer jobs | **PASS** — no jobs submitted |
| Owner mutation authorization | Task asked for execution; infrastructure missing so mutations stopped |

No production host was queried. Production custom domains were not used.

## 6. Scenario results

None executed. No timestamps beyond the Gate C probes.

| ID | Scenario | Classification |
| --- | --- | --- |
| S1 | Normal heartbeat | **NOT EXECUTED** |
| S2 | Worker termination | **NOT EXECUTED** (would also be unsafe on shared inline API) |
| S3 | Stale detection | **NOT EXECUTED** |
| S4 | Atomic recovery | **NOT EXECUTED** |
| S5 | Old worker resumption | **NOT EXECUTED** / remains **NOT VERIFIED** until a safe fence test exists |
| S6 | Credit integrity | **NOT EXECUTED** |
| S7 | Retry exhaustion | **NOT EXECUTED** |
| S8 | Result persistence | **NOT EXECUTED** |

Cleanup: no test jobs, reservations, workers, or temp files created.

## 7. Remaining gaps and remediation

1. Owner must re-provision or wake `docuflow-staging-*` in a dedicated
   Render workspace (`infra/render.staging.yaml`). Confirm Free Postgres
   has not expired (9.10D provisioned 7 Nov 2026; 30-day Free expiry).
2. Deploy staging API/cron from a SHA that includes 10.4B (`17dfe9c` or
   later; current main `0c97790`).
3. Confirm `/health` 200 and `/ready` database+storage true.
4. Provide isolated staging smoke credentials to the operator environment
   (`STAGING_API_URL`, `STAGING_HOST_CONFIRM`, `STAGING_SMOKE_*`). Do not
   paste secrets into chat.
5. Use Render Shell for SQL evidence. Do not use the agent `DATABASE_URL`.
6. For S2, do **not** restart the shared staging API. Prefer a
   single-job SQL backdate plus cleanup, or an isolated extra API
   instance if the owner adds one.
7. Re-run the 12-test plan in
   `docs/reports/PHASE_10_4B_R3_POST_MERGE_CI_AND_STAGING_READINESS.md`.

Phase 10.4C is not started.

## 8. Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Markdown lint | **not configured** |
| Full pytest | **not run** |
| Staging mutations | **not run** |
