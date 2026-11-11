# Phase 10.4B-SR4 — Post-merge reconciliation and staging readiness

Audit-only. Time: **11 Nov 2026, 16:30 Asia/Jakarta (WIB)**.
No application change. No staging mutation. No production access.

## Executive summary

Reconcile stale Phase 10.4B-SR3 **COMPLETE – UNMERGED** after PR #71
merged. Independently re-probe documented staging hosts. Phase 10.4B-S
remains **BLOCKED**.

| Item | Result |
| --- | --- |
| `origin/main` | `12151eeccfff37be45947d131f8cc6bed2858ec9` **VERIFIED** |
| PR #71 | **MERGED** **VERIFIED** |
| Main CI | [42993292238](https://github.com/mufea/docuflow-ai/actions/runs/42993292238) **SUCCESS** **VERIFIED** |
| Staging readiness | **BLOCKED** |
| 10.4B-S tests | **NOT EXECUTED** |

## GitHub and CI evidence

Owner-supplied targets matched independent GitHub CLI inspection.

| Field | Owner-reported | Independent result |
| --- | --- | --- |
| PR | #71 | [#71](https://github.com/mufea/docuflow-ai/pull/71) exists, base `main`, state **MERGED** |
| Merge SHA | `12151eeccfff37be45947d131f8cc6bed2858ec9` | `origin/main` HEAD is that SHA; merge `2026-11-11T09:12:59Z` / **16:12 Asia/Jakarta** |
| PR head | — | `af312a1acf2e1bdfe707f72e1749b526fb6eef03` |
| Main CI | `42993292238` SUCCESS | same run: `conclusion=success`, `headSha` matches, completed `2026-11-11T09:14:58Z` / **16:14 Asia/Jakarta** |
| Python | `130431108671` | SUCCESS |
| Web | `130431108857` | SUCCESS |

No later `main` push after this SHA. Limitation: Render dashboard was
not available; live service inventory is **UNKNOWN**.

Phase 10.4B implementation remains **MERGED** (PR #65, `17dfe9c`).

## Documentation reconciliation

On `12151ee`, `docs/IMPLEMENTATION_STATUS.md` still showed Phase
10.4B-SR3 **COMPLETE – UNMERGED**. GitHub merge evidence supersedes
that. This phase records **MERGED** for 10.4B-SR3. Staging and
production labels are unchanged.

## Staging readiness matrix

Public GET only. 11 Nov 2026, **16:30 Asia/Jakarta**
(`2026-11-11T09:30:46Z`). Prior 10.4B-S / SR / SR2 / SR3 probes are
**HISTORICAL**, not reused as current evidence.

| Component | Required | Evidence | Classification | Blocker |
| --- | --- | --- | --- | --- |
| API | Yes | HTTP 404 `x-render-routing: no-server` on `/health` and `/ready` | **BLOCKED** | B1 |
| Web | Yes | HTTP 404 `x-render-routing: no-server` | **BLOCKED** | B1 |
| PostgreSQL | Yes | `/ready` unreachable; agent DSN unused | **BLOCKED** | B1 |
| Worker | Architecture-dependent | Repo Blueprint `JOB_BROKER=inline`; no paid worker defined | **NOT APPLICABLE** (separate worker) / live **BLOCKED** | B1, B5 |
| Redis/Broker | Architecture-dependent | Omitted while inline | **NOT APPLICABLE** | — |
| Storage | Test-dependent | `/ready` unreachable; S3 keys `sync: false` in Blueprint | **BLOCKED** | B1 |
| Heartbeat | Yes | App default `JOB_HEARTBEAT_SECONDS=60` in `src/docuflow/config.py`; not pinned in Blueprint; live env **UNKNOWN** | **CONFIGURED** (repo) / **UNKNOWN** (live) | B3 |
| Recovery mechanism | Yes | Repo: cron `python -m docuflow.cleanup` `*/15`; live cron **UNKNOWN** | **CONFIGURED** (repo) / **BLOCKED** (live) | B1 |
| Test isolation | Yes | `STAGING_*` / smoke vars UNSET | **BLOCKED** | B2 |
| Migration compatibility | Yes | Cannot inspect Alembic on missing API | **UNKNOWN** | B1, B3 |
| 10.4B deploy SHA | Yes | Service absent | **MISSING** | B3 |
| Staging Blueprint | Yes | `infra/render.staging.yaml` | **VERIFIED** (repo only) | — |

Job mode designed: **inline**. Recovery designed: **fail+refund via
cleanup**, not a second worker reclaiming `processing`. Inline is
**not** accepted as RQ-worker evidence.

## Runtime scenarios (designed vs live)

| Scenario | Designed inline | Live |
| --- | --- | --- |
| Normal heartbeat | After API + 10.4B deploy | **NO** |
| Worker process-kill | **No** on shared Free API | **NO** |
| Stale detection | SQL backdate of one test job | **NO** |
| Atomic recovery | cleanup `fail_job_and_refund` | **NO** |
| Concurrent recovery | lease + claimed=0 | **NO** |
| Old worker resumption | fencing `status=processing` | **NO** |
| Fencing | heartbeat UPDATE requires `processing` | **NO** |
| Retry exhaustion | failed stays failed | **NO** |
| Credit integrity | `reserve:` / `refund:` / `settle:` | **NO** |
| Result persistence | after `/ready` storage true | **NO** |

S2 process-kill remains **NOT VERIFIED** by design on shared inline
(B5 **ACCEPTED**). That is not inline-as-fake-RQ.

## Blocker register

Confirmed:

| ID | Description | Severity | Evidence | Status | Why it matters | Owner action | Kind |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | No Render process on documented staging hosts | **CRITICAL** | 404 no-server at 16:30 | OPEN | Blocks all 10.4B-S tests | Inspect/re-apply `infra/render.staging.yaml` in dedicated staging workspace | infrastructure |
| B2 | Operator staging credentials unset | **CRITICAL** | env UNSET | OPEN | No isolated test identity | After B1, set `STAGING_*` locally, not in chat | configuration |
| B3 | No 10.4B SHA on live staging | **HIGH** | service absent | OPEN | Heartbeat code may be missing on live | Deploy API+cron from `17dfe9c` or later (`12151ee`) | infrastructure |
| B4 | Agent DSN is not staging Postgres | **HIGH** | SET; host not Render; name ≠ `docuflow_staging_db`; unused | OPEN | Prevents accidental wrong-DB SQL | SQL only in Render Shell on staging API | configuration / process |
| B5 | Must not restart shared inline API | **MEDIUM** | Blueprint `JOB_BROKER=inline` | **ACCEPTED** | Process-kill would take down all in-flight jobs | Use SQL backdate + cleanup | procedure |

Suspected (dashboard required; **not confirmed**): H1 services deleted;
H2 hostname/workspace changed; H3 auto-deploy off; H6 staging bucket
gone; H7 heartbeat env unset on Render.

Rejected (unchanged): H4 Free Postgres 30-day expiry as cause of 11 Nov
no-server (9.10D provisioned 7 Nov). H5 Free web spin-down (fast
no-server is not a cold start).

## 10.4B-S prerequisites (do not execute)

1. B1 closed: `/health` 200 and `/ready` database+storage true.
2. B3 closed: deploy SHA contains 10.4B (`17dfe9c` or later).
3. B2 closed: isolated smoke user and `STAGING_HOST_CONFIRM`.
4. Follow B4: never agent `DATABASE_URL`; never production hosts.
5. Cleanup cron or Render Shell one-shot.
6. Restore `JOB_STALE_MINUTES=90` after any drill override.
7. Owner authorization for mutations.

**Decision: BLOCKED.** UNKNOWN mandatory items (live DB, migrations,
storage, heartbeat env) also forbid READY.

## Safety

No application code, Blueprint apply, deploy, migration, job, credit,
storage, worker restart, or production DSN access. Agent `DATABASE_URL`
was classified by host-kind and database-name equality only.

## Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Full test suite | **not run** (docs-only) |
| Staging mutations | **not run** |
