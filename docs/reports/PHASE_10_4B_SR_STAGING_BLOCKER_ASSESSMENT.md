# Phase 10.4B-SR — Staging blocker investigation and remediation plan

Audit-only. Time: **11 Nov 2026, 15:50 Asia/Jakarta (WIB)**.
No application change. No staging mutation. No production access.

## 1. Objective

Explain why Phase 10.4B-S remains **BLOCKED** and list the minimum
owner actions to make a later 10.4B-S drill possible. Tests were **not**
executed.

## 2. Gate A — Main CI

| Field | Value |
| --- | --- |
| `origin/main` | `541c5b6122483afe82889e440f9c7ebf7e07a61c` |
| PR #68 | [#68](https://github.com/mufea/docuflow-ai/pull/68) **MERGED** |
| Merged at | `2026-11-11T08:47:31Z` / **11 Nov 2026, 15:47 Asia/Jakarta** |
| PR head | `f624b00be362f1a94b8b18b25362c8f0a3ce315c` |
| PR CI | [42989572346](https://github.com/mufea/docuflow-ai/actions/runs/42989572346) **SUCCESS** |
| Main push CI | [42989835663](https://github.com/mufea/docuflow-ai/actions/runs/42989835663) **SUCCESS** |
| Main CI completed | `2026-11-11T08:49:31Z` / **11 Nov 2026, 15:49 Asia/Jakarta** |
| Main Python | `130419717261` SUCCESS |
| Main Web | `130419717413` SUCCESS |

No intervening commits after `541c5b6`.

## 3. Inventory (11 Nov 2026)

Live HTTP was re-probed at **15:50 Asia/Jakarta**. Same result as 10.4B-S
(15:43): HTTP 404, `x-render-routing: no-server`, ~0.1s. Not a Free
spin-down (those typically stall then 502/503, then boot).

| Item | Classification | Evidence |
| --- | --- | --- |
| Staging Blueprint | **VERIFIED** (repo) | `infra/render.staging.yaml` |
| Staging API HTTP | **MISSING** / **BLOCKED** | 404 no-server |
| Staging web HTTP | **MISSING** / **BLOCKED** | 404 no-server |
| Staging PostgreSQL | **BLOCKED** | no `/ready`; no staging DSN here |
| Redis | **NOT APPLICABLE** | omitted while inline |
| Separate worker | **NOT APPLICABLE** | `JOB_BROKER=inline` |
| Cleanup cron | **BLOCKED** | cannot probe a missing stack |
| Object storage | **BLOCKED** | `/ready` unreachable |
| Heartbeat config | **CONFIGURED BUT NOT VERIFIED** | app default 60; not in Blueprint |
| Stale threshold | **CONFIGURED BUT NOT VERIFIED** | Blueprint `JOB_STALE_MINUTES=90` |
| Recovery retries | **NOT APPLICABLE** | 10.4B does not auto-retry `processing` |
| Isolated test account | **MISSING** | `STAGING_SMOKE_*` unset |
| Test credits | **MISSING** | no staging user |
| Alembic on staging | **NOT VERIFIED** | 9.10D was `0003`; not rechecked |
| 10.4B deploy SHA | **MISSING** | service absent |
| Operator staging env | **MISSING** | `STAGING_API_URL` unset |
| Agent `DATABASE_URL` | **BLOCKED** for this drill | not `docuflow_staging_db`; unused |

Phase 9.10D (7 Nov 2026) **STAGING VERIFIED** is historical functional
smoke + Alembic `0003`. It is not 10.4B-S evidence.

## 4. Runtime architecture (inline)

Staging and the default production stack run jobs **inside the API**
(`JOB_BROKER=inline`). Recovery is **fail+refund via cleanup**, not a
second worker reclaiming `processing`.

| Question | Answer |
| --- | --- |
| Independent worker claim? | Only `UPDATE … WHERE status=queued`. Two deliveries of the same `job_id` are safe. There is no separate worker process. |
| Safe worker termination? | **No** on the shared Free API. Restart kills every in-flight job. Forbidden by 10.4B-S. |
| Heartbeat in PostgreSQL? | Yes, after a 10.4B deploy: `jobs.heartbeat_at`. |
| Separate recovery process? | Yes: Render Cron `python -m docuflow.cleanup` (`*/15`) or a Render Shell one-shot. |
| Concurrent recovery? | Yes: cleanup lease + atomic fail claim. Two shells or overlapping cron. |
| Fencing? | `status=processing` on heartbeat, complete, and stale fail. No owner token. |
| Credit inspect? | Ledger keys `reserve:` / `settle:` / `refund:` + `{job_id}` in staging Postgres via Render Shell. |
| Result download? | Yes, after API is up, using isolated smoke login. |

Inline **can** exercise 10.4B once the API exists. It **cannot** prove
a dedicated RQ worker. Do not label separate-worker recovery VERIFIED.

Safe stand-in for “worker death”: let the test job stay `processing`
after a **single-job** SQL backdate of `heartbeat_at`, then run cleanup.
Do not restart `docuflow-staging-api`.

## 5. Confirmed blockers

| ID | Severity | Description | Evidence | Root cause | Owner action | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | **CRITICAL** | Documented staging API/web have no Render process | HTTP 404 `x-render-routing: no-server` at 15:43 and 15:50 Asia/Jakarta | **UNKNOWN**. Confirmed only that DNS hits Render and no server is attached. | In the dedicated staging workspace, inspect whether `docuflow-staging-api` / `web` / `db` / `cleanup` exist, are suspended, or were deleted. Re-apply `infra/render.staging.yaml` only in that workspace. | Owner dashboard + optional Blueprint apply |
| B2 | **CRITICAL** | No isolated staging operator credentials in this environment | `STAGING_API_URL` and smoke vars UNSET | Confirmed absence | After B1, set `STAGING_API_URL`, `STAGING_HOST_CONFIRM`, `STAGING_SMOKE_*` on the operator machine. Do not paste secrets into chat. | Config inject |
| B3 | **HIGH** | No 10.4B SHA on a live staging API | Cannot read a missing service | Confirmed missing evidence, not a code defect | Deploy staging API/cron from `17dfe9c` or later (current main `541c5b6`) | Render deploy |
| B4 | **HIGH** | Agent `DATABASE_URL` is not the 9.10D staging database name | Identity ≠ `docuflow_staging_db`; unused | Confirmed mismatch | Never use the agent DSN. SQL only in Render Shell on staging API. | Process |
| B5 | **MEDIUM** | Shared inline API cannot be killed as a “test worker” | Architecture in `infra/render.staging.yaml` + OPERATIONS.md | Confirmed design | Use SQL backdate + cleanup for stale/fencing tests. Do not restart the shared API. | Procedure only |

Dependencies: B2, B3, and all 10.4B-S tests depend on B1.

## 6. Suspected (not confirmed)

| ID | Severity | Hypothesis | Why unconfirmed | How to confirm |
| --- | --- | --- | --- | --- |
| H1 | HIGH | Staging services deleted | Matches no-server; no dashboard access | Owner lists Render services |
| H2 | MEDIUM | Hostname or workspace changed | 9.10D used these hosts; 404 does not prove rename | Owner compares live URLs |
| H3 | LOW | Auto-deploy off after 9.10D | Would not by itself remove routing | Owner inspects deploy history |
| H4 | — | Free Postgres 30-day expiry | **Rejected as cause for 11 Nov 2026.** 9.10D provisioned **7 Nov 2026**; Free expiry is ~30 days later (~7 Dec). | Still confirm remaining days in dashboard |
| H5 | — | Free web spin-down | **Rejected.** 0.1s `no-server` is not a cold start. | n/a |
| H6 | MEDIUM | Staging bucket or S3 keys gone | `/ready` unreachable so storage unknown | After API is up, `/ready` `storage` |
| H7 | LOW | `JOB_HEARTBEAT_SECONDS` unset on Render | Blueprint does not pin it; app default 60 after 10.4B deploy | Env panel after B3 |

## 7. Minimum remediation (no app change)

1. **Owner:** open the dedicated staging Render workspace (must contain
   `docuflow-staging-*` only; must not contain `docuflow-api` /
   `docuflow-db`).
2. **Owner:** if services are missing, apply `infra/render.staging.yaml`
   there. Do not apply `infra/render.yaml`. Confirm Free Postgres
   remaining days.
3. **Owner:** deploy API + cleanup from main `541c5b6` or later (includes
   10.4B `17dfe9c`). Optionally set `JOB_HEARTBEAT_SECONDS=60`.
4. **Owner:** GET `/health` 200 and `/ready` with `database` and
   `storage` true. Record the deployed SHA from Render.
5. **Owner:** keep smoke credentials on the operator machine; authorize
   `STAGING_SMOKE_MUTATIONS=1` for a later 10.4B-S run.
6. **Operator (later phase):** Render Shell SQL only. Never agent
   `DATABASE_URL`. Never production hosts.

No new Redis, worker, or schema. No application PR unless a later
drill proves a code defect.

Optional future PR (not this phase): pin `JOB_HEARTBEAT_SECONDS=60` in
`infra/render.staging.yaml`. Not required for the drill.

## 8. Later 10.4B-S checklist (do not execute)

Owner authorization required for every mutating step.

Global preconditions: B1–B3 closed; `/health` `/ready` pass; inline
broker; cron or Shell cleanup; dedicated test user with credits;
Render Shell; `JOB_STALE_MINUTES` restored to 90 after any drill
override.

| Test | Services | Config | Steps (summary) | Expected | Evidence | Cleanup |
| --- | --- | --- | --- | --- | --- | --- |
| S1 heartbeat | API, DB, storage | default 60s | Submit isolated job; SQL `heartbeat_at` at claim / after complete | Processing beat; terminal not refreshed; one `settle:{id}` | timestamps, ledger | delete test PDF |
| S2 termination | **do not restart API** | — | **Substitute:** leave job processing; do not kill API | See S3 | note S2 NOT VERIFIED as process-kill | continue S3 |
| S3 stale detect | API Shell | backdate **test job only** | SELECT stale clause | test job candidate; healthy jobs excluded | job ids | S4 |
| S4 atomic recover | cleanup cron or Shell | — | one `python -m docuflow.cleanup` | `failed`/`timeout`; one `refund:{id}` | row, ledger, logs | delete docs |
| S5 concurrent | two Shells | — | two cleanups | one lease skip or claimed=0; one refund | logs | same |
| S6 old worker | after S4 | — | confirm no late complete/settle | stays failed; no settle | status, ledger | none |
| S7 fencing | live beat vs cleanup | fresh heartbeat | cleanup while beat new | claimed=0; still processing | row | complete or backdate |
| S8 retry | failed job | — | cleanup again; API boot | stays failed; no requeue | status, attempt | none |
| S9 credits reserve | S3–S4 | isolated user | ledger | one reserve, one refund, second cleanup no-op | keys | none |
| S10 credits settle | S1 | — | cleanup after complete | no refund of settled job | ledger | delete results |
| S11 results | S1 vs S4 | — | compare documents | completed has files; lost-ownership has none | document ids | API delete |
| S12 audit | logs | `LOG_JSON=true` | collect heartbeat/fail/cleanup lines | no secrets | redacted logs | none |

S2 process-kill remains **NOT VERIFIED** by design on shared inline.
That does not block fail+refund verification via S3–S7.

## 9. Files inspected

`docs/IMPLEMENTATION_STATUS.md`,
`docs/reports/PHASE_10_4B_S_STAGING_VERIFICATION.md`,
`docs/reports/PHASE_10_4B_R3_POST_MERGE_CI_AND_STAGING_READINESS.md`,
`docs/reports/PHASE_10_4B_JOB_HEARTBEAT_STALE_RECOVERY.md`,
`docs/OPERATIONS.md`, `docs/DEPLOYMENT.md`, `docs/staging.env.example`,
`infra/render.staging.yaml`. No `src/` edits.

## 10. Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Markdown lint | **not configured** |
| Staging mutations | **not run** |
| Production access | **none** |
