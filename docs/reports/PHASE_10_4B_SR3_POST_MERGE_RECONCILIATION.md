# Phase 10.4B-SR3 — Post-merge reconciliation and staging reassessment

Audit-only. Time: **11 Nov 2026, 16:09 Asia/Jakarta (WIB)**.
No application change. No staging mutation. No production access.

## 1. Gate A — Baseline

| Field | Value |
| --- | --- |
| `origin/main` | `fe1f0d0ea4b5301f159be1ea72afc7413b02f0f0` |
| PR #70 | [#70](https://github.com/mufea/docuflow-ai/pull/70) **MERGED** |
| Merged at | `2026-11-11T09:03:44Z` / **11 Nov 2026, 16:03 Asia/Jakarta** |
| PR head | `81d91b967344a5042a1d2691d006cf69489770e8` |
| Main push CI | [42991996035](https://github.com/mufea/docuflow-ai/actions/runs/42991996035) **SUCCESS** |
| Main CI completed | `2026-11-11T09:05:57Z` / **11 Nov 2026, 16:05 Asia/Jakarta** |
| Main Python | `130426889629` SUCCESS |
| Main Web | `130426889791` SUCCESS |

No intervening `main` commits after `fe1f0d0`. Phase 10.4B
implementation remains **MERGED** (PR #65, `17dfe9c`).

## 2. Gate B — Documentation reconciliation

`docs/IMPLEMENTATION_STATUS.md` on `fe1f0d0` still showed Phase
10.4B-SR2 **COMPLETE – UNMERGED**. GitHub evidence supersedes that:

- PR [#70](https://github.com/mufea/docuflow-ai/pull/70) **MERGED**
- Merge commit `fe1f0d0ea4b5301f159be1ea72afc7413b02f0f0`
- Main CI **SUCCESS** as above

This phase records **MERGED** for 10.4B-SR2. Staging and production
labels are unchanged.

## 3. Gate C — Independent staging re-probe

Public GET only. 11 Nov 2026, **16:09 Asia/Jakarta**
(`2026-11-11T09:09:42Z`). Previous 10.4B-S / SR / SR2 probes are not
reused as current evidence.

| Target | Result |
| --- | --- |
| `https://docuflow-staging-api.onrender.com/health` | HTTP 404 `x-render-routing: no-server` |
| `https://docuflow-staging-api.onrender.com/ready` | HTTP 404 `x-render-routing: no-server` |
| `https://docuflow-staging-web.onrender.com/` | HTTP 404 `x-render-routing: no-server` |

Response ~0.1s. Cloudflare `server` present. This is missing Render
process routing, not a measured Free cold start.

| Item | Classification | Evidence |
| --- | --- | --- |
| Staging Blueprint | **VERIFIED** (repo) | `infra/render.staging.yaml` |
| API HTTP | **MISSING** / **BLOCKED** | 404 no-server |
| Web HTTP | **MISSING** / **BLOCKED** | 404 no-server |
| PostgreSQL | **BLOCKED** | `/ready` unreachable; no staging DSN used |
| Redis | **NOT APPLICABLE** | Blueprint omits Redis while `JOB_BROKER=inline` |
| Separate worker | **NOT APPLICABLE** | inline API process |
| Recovery mechanism | **CONFIGURED BUT NOT VERIFIED** | repo: cron `python -m docuflow.cleanup` `*/15` |
| Object storage | **BLOCKED** | `/ready` unreachable |
| Job execution mode | **CONFIGURED** (repo) / **NOT VERIFIED** (live) | `JOB_BROKER=inline` |
| Heartbeat env | **CONFIGURED BUT NOT VERIFIED** | app default 60s; not pinned in Blueprint |
| Stale threshold | **CONFIGURED BUT NOT VERIFIED** | Blueprint `JOB_STALE_MINUTES=90` |
| Processing auto-retry | **NOT APPLICABLE** | 10.4B does not requeue `processing` |
| Operator `STAGING_*` | **MISSING** | `STAGING_API_URL` / `STAGING_HOST_CONFIRM` / smoke vars UNSET |
| Schema / Alembic on staging | **NOT VERIFIED** | cannot inspect a missing API |
| 10.4B deploy SHA | **MISSING** | service absent |
| Agent `DATABASE_URL` | **BLOCKED** for this drill | SET, host not Render, db name ≠ `docuflow_staging_db`; unused |

Phase 9.10D (7 Nov 2026) **STAGING VERIFIED** is historical functional
smoke. It is not 10.4B-S evidence and does not prove current hosts.

## 4. Gate D — Runtime architecture

Designed staging recovery is **fail+refund via cleanup**, not a second
worker reclaiming `processing`. Inline is the documented staging and
default production mode. Separate-worker (RQ) evidence is **not**
accepted as equivalent and is **not** required for 10.4B-S on this
stack.

| Scenario | Inline (designed) | Live now | Separate-worker equivalent? |
| --- | --- | --- | --- |
| 1. Normal heartbeat | Yes after API+10.4B deploy | **NO** | Not required |
| 2. Worker termination | **No** — killing API kills all in-flight jobs | **NO** | Would need paid worker; not provisioned |
| 3. Stale detection | Yes: SQL backdate of **one** test job | **NO** | Not required |
| 4. Atomic recovery | Yes: cleanup claim `fail_job_and_refund` | **NO** | Not required |
| 5. Concurrent recovery | Yes: lease + claimed=0 | **NO** | Not required |
| 6. Old worker resumption | Yes: fencing on `status=processing` | **NO** | Process-kill still not safe on shared API |
| 7. Fencing | Yes: heartbeat UPDATE requires `processing` | **NO** | No owner UUID token |
| 8. Retry exhaustion | Yes: failed stays failed | **NO** | Not required |
| 9. Credit integrity | Yes: `reserve:` / `refund:` / `settle:` | **NO** | Not required |
| 10. Result persistence | Yes after `/ready` storage true | **NO** | Not required |

S2 process-kill remains **NOT VERIFIED** by design on shared inline.
That is accepted (B5). It is **not** inline-as-fake-RQ evidence.

## 5. Gate E — Blockers

Confirmed:

| ID | Description | Evidence | Severity | Owner action | Closure |
| --- | --- | --- | --- | --- | --- |
| B1 | No Render process on documented staging hosts | 404 no-server at 16:09 | **CRITICAL** | Inspect/re-apply `infra/render.staging.yaml` in dedicated staging workspace | `/health` 200; `/ready` database+storage true |
| B2 | Operator staging credentials unset | env UNSET | **CRITICAL** | After B1, set `STAGING_*` locally | URL + host confirm match live API |
| B3 | No 10.4B SHA on live staging | service absent | **HIGH** | Deploy API+cron from `17dfe9c` or later (`fe1f0d0`) | Render deploy SHA recorded |
| B4 | Agent DSN is not staging Postgres | SET; not Render; name ≠ `docuflow_staging_db`; unused | **HIGH** | SQL only in Render Shell on staging API | no agent DSN opened |
| B5 | Must not restart shared inline API | Blueprint `JOB_BROKER=inline` | **MEDIUM** | SQL backdate + cleanup | **ACCEPTED** |

Suspected (not confirmed; dashboard required):

| ID | Hypothesis | Why unconfirmed |
| --- | --- | --- |
| H1 | Staging services deleted | Matches no-server; no dashboard |
| H2 | Hostname or workspace changed | 9.10D used these hosts; 404 ≠ rename proof |
| H3 | Auto-deploy off | Would not by itself remove routing |
| H6 | Staging bucket/keys gone | `/ready` unreachable |
| H7 | `JOB_HEARTBEAT_SECONDS` unset on Render | Blueprint does not pin it |

Rejected (unchanged): H4 Free Postgres 30-day expiry as cause of 11 Nov
no-server (9.10D provisioned 7 Nov). H5 Free web spin-down (0.1s
no-server is not a cold start).

## 6. Owner actions (not executed)

Same minimum as 10.4B-SR2, with deploy target `fe1f0d0` or later:

1. Dedicated staging workspace only (`docuflow-staging-*`).
2. List services; note missing vs suspended vs deleted.
3. If missing, apply **only** `infra/render.staging.yaml`.
4. Deploy from `main` `fe1f0d0` or later.
5. Record `/health` `/ready` and deploy SHA (no secrets).
6. Keep smoke credentials off-chat. Authorize 10.4B-S mutations later.

## 7. 10.4B-S prerequisites (do not execute)

B1–B3 closed. Isolated test user. Render Shell. Cleanup cron or
one-shot. `JOB_STALE_MINUTES` restored to 90 after any drill override.
Never agent `DATABASE_URL`. Never production hosts.

**Decision: BLOCKED.**

## 8. Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Staging mutations | **not run** |
| Production access | **none** |
