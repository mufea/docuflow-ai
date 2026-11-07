# Phase 9.10D — Owner verification execution

Owner-assisted evidence only. No application-code changes. No schema upgrade
was run in this phase. Credentials, DSNs, cookies, and emails are not recorded.

## 1. Repository baseline

| Item | Value |
| --- | --- |
| Repository | https://github.com/mufea/docuflow-ai |
| `origin/main` at start | `17182e56c337948bed3bbbf448597a9814d2cc6f` (PR #19 merge) |
| PR #19 | **MERGED** 7 Nov 2026, 10:17 Asia/Jakarta |
| Prior report | `docs/reports/PHASE_9_10C_STAGING_VERIFICATION.md` |
| Evidence timestamp | 7 Nov 2026, 15:07 Asia/Jakarta (WIB) |

## 2. Hosted migration verification

Owner ran a **read-only** inspect in Render Shell on `docuflow-staging-api`
(`~/project/src`). The inspect used `SELECT 1` and `SELECT version_num FROM
alembic_version` plus `python -m alembic current` / `heads`. It did **not**
run `STAGING_MIGRATE=1`, `alembic upgrade`, or `python -m docuflow.migrate`.

Sanitized owner output:

```
host=dpg-dbn71tec6qcc73cric9g-a database=docuflow_staging_db
select_1 ok
alembic_current 0003_cost_efficient_reliability
expected_head 0003_cost_efficient_reliability
matches_head True
heads ['0003_cost_efficient_reliability']
multiple_heads False
schema_mutated False
```

`python -m alembic current` and `python -m alembic heads` both reported
`0003_cost_efficient_reliability (head)`.

| Check | Result | Evidence |
| --- | --- | --- |
| Render API Shell | PASS | Prompt `render@srv-…:~/project/src` on staging API |
| Database connection | PASS | `select_1 ok`; database name `docuflow_staging_db` |
| Current revision | PASS | `0003_cost_efficient_reliability` |
| Expected migration head | PASS | same revision |
| Pending migrations | none | `matches_head True` |
| Multiple heads | none | `multiple_heads False`; one Alembic head |
| Schema mutation performed | **NO** | `schema_mutated False`; no upgrade command |

Host is a Render private Postgres hostname (`dpg-…-a`), not `docuflow-db`.
Name contains `staging`.

## 3. Cross-user isolation

Owner-run against `https://docuflow-staging-api.onrender.com` from the laptop
with `uv run python` (no `docuflow` import). Two dedicated staging sessions.
No cookies, emails, or passwords recorded.

| Test | Result | HTTP |
| --- | --- | --- |
| User A login | PASS | 200 |
| User B login | PASS | 200 |
| User A upload | PASS | 200 (`doc_id SET`) |
| User A own access | PASS | GET 200 |
| User B metadata access | PASS | GET 403 |
| User B download | PASS | 403 |
| User B delete | PASS | DELETE 403 |
| User A access after test | PASS | GET 200 |
| Cleanup (User A delete) | PASS | 200 |
| Unauthenticated access | PASS | GET 401 |

This matches the existing policy: other-user access is **403**, missing
session is **401**. Live isolation is no longer only a local unit-test result.

## 4. Code changes

Application code changed: **NO**.

This phase updates documentation and evidence only.

## 5. Outstanding blockers

None for the two 9.10C remaining gates.

Residual (not blockers for STAGING VERIFIED):

- Download content checksum is still not in the smoke client (HTTP 302 by design).
- Cleanup cron is not independently timed beyond API DELETE 200.
- Production is out of scope.

## 6. Final staging decision

**STAGING VERIFIED**

Required gates now have evidence: provisioned staging, provider test, non-mutating
HTTP, mutating lifecycle (9.10B), hosted Alembic head `0003`, and live
cross-user 403/401.

**STAGING FUNCTIONAL VERIFIED** remains YES (lifecycle). It is not a substitute
label here; the remaining 9.10C blockers are closed.

## 7. Production status

**NOT DEPLOYED. NOT VERIFIED. NOT AUTHORIZED.**
