# Phase 10.4B-R3 — Post-merge CI reconciliation and staging readiness

Documentation-only. Time: **11 Nov 2026, 15:37 Asia/Jakarta (WIB)**.
Does **not** deploy, mutate staging, or execute the 10.4B-S plan.

## 1. Objective and baseline

Record PR #66 merge and main push CI SUCCESS. Correct the stale
Phase 10.4B-R2 **COMPLETE – UNMERGED** label. Audit staging
prerequisites for Phase 10.4B-S. No application, schema, or
infrastructure change except documenting heartbeat env defaults.

| Item | Value |
| --- | --- |
| Mandatory baseline | `a5a814bd5d47ed5cf6c5ff265e2952566096eac1` |
| `origin/main` at branch creation | `a5a814bd5d47ed5cf6c5ff265e2952566096eac1` |
| Feature branch | `docs/phase-10-4b-r3-post-merge-reconciliation` |
| Target | `main` |

Working tree was clean. Branch created from `origin/main`. No reset.

## 2. Gate A — PR #66 and CI

Verified with `gh pr view 66`, `gh run view`, and `git fetch origin main`
before editing. Supplied historical values matched.

| Field | Value |
| --- | --- |
| PR | [#66](https://github.com/mufea/docuflow-ai/pull/66) **MERGED** |
| Title | docs(phase-10.4b): reconcile merged implementation and CI evidence |
| PR head | `b900d5beb77e4e376fdf3f3b59229989300602f8` |
| Merge commit / `origin/main` | `a5a814bd5d47ed5cf6c5ff265e2952566096eac1` |
| Merged at | `2026-11-11T08:30:14Z` / **11 Nov 2026, 15:30 Asia/Jakarta** |
| PR CI | [42987402176](https://github.com/mufea/docuflow-ai/actions/runs/42987402176) **SUCCESS** on `b900d5b` |
| Main push CI | [42987548255](https://github.com/mufea/docuflow-ai/actions/runs/42987548255) **SUCCESS** on `a5a814b` |
| Main CI completed | `2026-11-11T08:31:56Z` / **11 Nov 2026, 15:31 Asia/Jakarta** |

Main push jobs: Python `130412244345` SUCCESS (unit, PostgreSQL
integration, lint, typecheck); Web `130412244660` SUCCESS (lint,
typecheck, tests, production build). PR Python `130411757702` finished
**after** the merge and is also SUCCESS.

PR CI SUCCESS is not a substitute for main push CI. Main push CI
SUCCESS is not staging or production verification.

Phase 10.4B implementation remains **MERGED** (PR
[#65](https://github.com/mufea/docuflow-ai/pull/65), merge `17dfe9c`).

## 3. Gate B — Documentation labels

| Label | Before (on `main`) | After |
| --- | --- | --- |
| 10.4B implementation | **MERGED** (PR #65) | **MERGED** (unchanged) |
| 10.4B-R2 | **COMPLETE – UNMERGED** | **MERGED** (PR #66, merge `a5a814b`) |
| 10.4B-R3 | (absent) | **COMPLETE – UNMERGED** (this PR) |
| Staging (10.4B heartbeat) | **NOT VERIFIED** | **NOT VERIFIED** |
| Deployment | **NOT DEPLOYED** | **NOT DEPLOYED** |
| Production | **NOT VERIFIED** | **NOT VERIFIED** |

Phase 9.15, backup, and DR labels are unchanged.

## 4. Gate C — Staging infrastructure assessment

Sources: `infra/render.staging.yaml`, `docs/staging.env.example`,
`docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`, `scripts/staging_*.py`,
Phase 9.10B–D reports. **This phase did not contact Render, staging
hosts, or any database.** Historical 9.10D evidence (7 Nov 2026) is not
proof that services, plans, or deployed SHAs are unchanged on 11 Nov
2026.

Do not treat Phase 9.10D **STAGING VERIFIED** (functional smoke +
Alembic `0003`) as Phase 10.4B heartbeat/stale-recovery verification.

| Item | Classification | Notes |
| --- | --- | --- |
| Staging Blueprint template | **VERIFIED** (repo) | `infra/render.staging.yaml` parses; isolated `docuflow-staging-*` names |
| Staging API service | **CONFIGURED BUT NOT VERIFIED** | Template + 9.10D live attestation; 10.4B SHA deploy **NOT VERIFIED** |
| Staging web service | **CONFIGURED BUT NOT VERIFIED** | Same |
| Staging PostgreSQL | **CONFIGURED BUT NOT VERIFIED** | 9.10D: `docuflow_staging_db`, Free, 30-day expiry; live presence not rechecked |
| Redis | **NOT APPLICABLE** | Omitted while `JOB_BROKER=inline` |
| Paid / RQ worker | **NOT APPLICABLE** | Inline pool on the API |
| Job execution mode | **CONFIGURED BUT NOT VERIFIED** | Blueprint `JOB_BROKER=inline`, `WORKER_CONCURRENCY=2`, timeout 300s |
| Heartbeat interval | **CONFIGURED BUT NOT VERIFIED** | **Not pinned** in staging Blueprint. App default `JOB_HEARTBEAT_SECONDS=60` after a 10.4B deploy. `0` disables the timer only |
| Stale threshold | **CONFIGURED BUT NOT VERIFIED** | Blueprint `JOB_STALE_MINUTES=90`; floor remains worker timeout + grace |
| Recovery scheduler | **CONFIGURED BUT NOT VERIFIED** | Cron `docuflow-staging-cleanup` `*/15`; API `CLEANUP_INTERVAL_SECONDS=0` |
| Cleanup lease | **CONFIGURED BUT NOT VERIFIED** | `CLEANUP_LEASE_MINUTES=5` on API and cron |
| Object storage | **CONFIGURED BUT NOT VERIFIED** | Dedicated staging bucket attested 9.10D; `/ready` storage true then |
| Required env (secrets) | **CONFIGURED BUT NOT VERIFIED** | Owner-supplied S3; Render `DATABASE_URL` / secret key. Values not in this environment |
| `JOB_HEARTBEAT_SECONDS` in Blueprint | **MISSING** | Relies on application default after deploy |
| 10.4B deploy on staging | **MISSING** | No evidence staging runs `f1802a0` / `17dfe9c` / `a5a814b` |
| 10.4B-S smoke script | **MISSING** | Existing `staging_smoke.py` does not inspect `heartbeat_at` or stale fail |
| SQL observe path | **CONFIGURED BUT NOT VERIFIED** | `ipAllowList: []`; use Render Shell on staging API, not a laptop DSN |
| Temporary stale-drill override | **MISSING** | Not in Blueprint; operator-only, restore after drill |
| Production DSNs | **NOT APPLICABLE** | Must not be used |

### Missing prerequisites for Phase 10.4B-S execution

1. Owner confirms staging workspace still has only `docuflow-staging-*`
   services and Free Postgres has not expired.
2. Owner deploys staging API/cron from a SHA that includes Phase 10.4B
   (`17dfe9c` or later; current main `a5a814b`).
3. Owner optionally sets staging API `JOB_HEARTBEAT_SECONDS=60` explicitly.
4. Owner-operated Render Shell (or equivalent) for SQL evidence. No
   production DSN. Do not open `ipAllowList` to the public internet.
5. Dedicated staging test account. No production users or jobs.
6. Authorization to run mutating staging tests (`STAGING_SMOKE_MUTATIONS=1`
   plus SQL/log inspect). This phase does **not** run them.

## 5. Phase 10.4B-S test plan (do not execute here)

Safety for every test:

- Staging hosts and staging database only.
- Never print `DATABASE_URL`, passwords, cookies, or signed URLs.
- Do not point `STAGING_*` at production custom domains.
- Restore `JOB_STALE_MINUTES=90` and any heartbeat override after the drill.
- Fail leftover test jobs (`timeout` / cleanup) so credits refund once.
- Do not apply `infra/render.yaml`.
- Do not start Phase 10.4C.

Global preconditions:

- Staging API/web `/health` 200 and `/ready` database+storage true.
- Deployed SHA contains 10.4B heartbeat code.
- `JOB_BROKER=inline`. Cron `*/15` exists or owner can run
  `python -m docuflow.cleanup` in Render Shell.
- Test user has reserved credits available.

Evidence to keep: job id, status, `heartbeat_at` / `started_at` (timestamps
only), ledger idempotency key names (`reserve:` / `settle:` / `refund:` +
job id), log lines without secrets, HTTP status codes.

### 1. Normal heartbeat

- **Preconditions:** Staging runs 10.4B; submit a short `extract_text` (or
  equivalent mock) job as the test user.
- **Procedure:** While `status=processing`, read `heartbeat_at` from
  staging SQL in Render Shell at claim, during the job if it lasts >60s,
  and after completion.
- **Expected:** `heartbeat_at` is set at claim; terminal rows are not
  refreshed afterward; completed job settles once (`settle:{job_id}`).
- **Evidence:** SQL timestamps; job `completed`; one settle row; no refund.
- **Cleanup:** None if completed; delete uploaded test PDF via API.
- **Safety:** Staging job only; do not dump full `result_payload`.

### 2. Worker termination

- **Preconditions:** Inline API is the worker. Start a job, confirm
  `processing`.
- **Procedure:** Restart or stop `docuflow-staging-api` during
  `processing` (Render deploy/restart). Do not wait for stale cleanup yet.
- **Expected:** Row stays `processing`. Heartbeats stop. `queued` re-enqueue
  on boot does not reset `processing`.
- **Evidence:** Status still `processing` after API up; `attempt` unchanged;
  no second `reserve:{job_id}`.
- **Cleanup:** Continue into tests 3–4 or fail+refund via cleanup.
- **Safety:** One test job. Do not restart production.

### 3. Stale job detection

- **Preconditions:** A `processing` row with old liveness. Prefer SQL
  backdate of **that test job only**: set `heartbeat_at` (and `started_at`
  if needed) older than `effective_stale_minutes()`. Waiting 90 minutes
  after a kill is valid but slow. Do not lower stale minutes below the
  worker-timeout floor.
- **Procedure:** `SELECT` processing rows matching
  `stale_processing_clause`. Do not fail yet.
- **Expected:** Test job is a candidate. Healthy jobs with fresh
  `heartbeat_at` are not.
- **Evidence:** Candidate job id; excluded healthy job id if one exists.
- **Cleanup:** Immediate fail via test 4 so it does not sit until cron.
- **Safety:** Backdate only the dedicated test job.

### 4. Atomic recovery (fail+refund)

- **Preconditions:** Candidate from test 3.
- **Procedure:** Run `python -m docuflow.cleanup` once in staging API
  shell, or wait for cron.
- **Expected:** One `failed` / `error_code=timeout`; one
  `refund:{job_id}`; `credits_reserved` released; not `completed`.
- **Evidence:** Job row; ledger; cleanup log
  `abandoned_job_failed` / `job_failed_refunded`.
- **Cleanup:** Delete test documents.
- **Safety:** Recovery is fail+refund, not resume.

### 5. Concurrent recovery attempts

- **Preconditions:** Another stale test job (or rerun 2–3).
- **Procedure:** Start two cleanup processes nearly together (two shells
  or overlapping manual cron).
- **Expected:** One lease skip or one `claimed=0`. Single refund row.
  Terminal status once.
- **Evidence:** `cleanup_skipped reason=lease_held` and/or one refund.
- **Cleanup:** Same as test 4.
- **Safety:** Staging only; do not loop cleanup against production.

### 6. Old worker resumption

- **Preconditions:** Test 2 job still `processing` on a dying/restarted
  worker **or** fail it first (test 4) then simulate a late complete.
- **Procedure:** After cleanup has failed the job, confirm no later
  complete/settle. If a late in-process worker still holds files, it must
  skip `store_result` / settle (`JobStateError` / zero-row complete).
- **Expected:** Status remains `failed`. No `settle:{job_id}`. No new
  result documents.
- **Evidence:** Status, ledger, `documents` count for the test user.
- **Cleanup:** Refund already done; delete any leaked temp only in
  workdir (ephemeral).
- **Safety:** Do not re-queue the failed job.

### 7. Fencing protection

- **Preconditions:** One `processing` test job with a fresh heartbeat.
- **Procedure:** Invoke stale fail (`fail_job_and_refund` via cleanup)
  while `heartbeat_at` is newer than cutoff. Optionally touch heartbeat
  then cleanup.
- **Expected:** Fail claim does not match. Job stays `processing`. No
  refund. Heartbeat skip on terminal jobs remains false-update.
- **Evidence:** `claimed=0` / still `processing`; empty `refund:{job_id}`.
- **Cleanup:** Complete the job normally or fail only after backdating.
- **Safety:** Do not backdate a live user job.

### 8. Retry exhaustion

- **Preconditions:** 10.4B does not auto-retry `processing`.
- **Procedure:** Observe a failed stale job. Confirm it is not returned
  to `queued` by cleanup or API boot re-enqueue (re-enqueue is `queued`
  only). `attempt` increments only on `queued` → `processing` claim.
- **Expected:** No unbounded retry. Failed remains failed.
- **Evidence:** Status history; `attempt` value; boot logs.
- **Cleanup:** None.
- **Safety:** Do not manually set `status=queued` on a billed job.

### 9. Credit reservation integrity

- **Preconditions:** Known starting `available` credits for the test user.
- **Procedure:** Submit job (reserve), then recover via fail+refund
  (tests 3–4). Repeat cleanup.
- **Expected:** One `reserve:{job_id}`. One `refund:{job_id}`. Second
  cleanup does not reserve or refund again. Available credits restored.
- **Evidence:** Ledger keys and `released` / `already_refunded`.
- **Cleanup:** None.
- **Safety:** Do not settle a failed job.

### 10. Credit settlement integrity

- **Preconditions:** Test 1 completed job.
- **Procedure:** Inspect ledger. Run cleanup. Attempt a duplicate settle
  is not required if runner already no-ops; confirm no `refund:{job_id}`
  on a settled job.
- **Expected:** One `settle:{job_id}`. Cleanup does not refund settled
  work. Balance decreased by reserved amount once.
- **Evidence:** Ledger; `credits_settled`.
- **Cleanup:** Delete result documents after download check if needed.
- **Safety:** Settled jobs must stay settled.

### 11. Result persistence

- **Preconditions:** Pair of jobs: one completed (test 1), one
  lost-ownership failed (tests 2–6).
- **Procedure:** Compare `result_document_ids` and storage objects.
- **Expected:** Completed job has result documents. Failed lost-ownership
  job has none (10.3C `store_result(commit=False)` + skipped complete).
- **Evidence:** Document rows; no orphan user-visible results for the
  failed job. Storage orphans after rollback remain an accepted 10.3C
  limitation if objects were uploaded before rollback — record if seen.
- **Cleanup:** API delete of test documents.
- **Safety:** Do not delete unrelated staging files.

### 12. Recovery auditability

- **Preconditions:** JSON logs (`LOG_JSON=true` on staging).
- **Procedure:** Collect log lines for heartbeat skip/fail, abandoned
  fail, cleanup skip/lease.
- **Expected:** `job_heartbeat_skipped`, `job_heartbeat_failed` (only if
  induced), `job_failed_refunded`, `abandoned_job_failed`,
  `cleanup_skipped` / `cleanup_finished` without secrets or DSNs.
- **Evidence:** Redacted log excerpts with job ids.
- **Cleanup:** None.
- **Safety:** Redact URLs and tokens before storing evidence.

## 6. Files inspected

- `docs/IMPLEMENTATION_STATUS.md`
- `docs/reports/PHASE_10_4B_JOB_HEARTBEAT_STALE_RECOVERY.md`
- `docs/reports/PHASE_10_4B_POST_MERGE_RECONCILIATION.md`
- `docs/OPERATIONS.md`
- `docs/DEPLOYMENT.md`
- `docs/staging.env.example`
- `infra/render.staging.yaml`
- `scripts/staging_smoke.py`, `scripts/staging_preflight.py`,
  `scripts/staging_migrate_verify.py`
- `docs/reports/PHASE_9_10D_OWNER_VERIFICATION.md`

No files under `src/`, `tests/` (except not modified), Alembic, or
production `infra/render.yaml`.

## 7. Remaining gaps

- 10.4B not shown deployed on staging.
- Live staging service health on 11 Nov 2026: **NOT VERIFIED**.
- Heartbeat / stale-fail drill: **NOT EXECUTED**.
- Production: **NOT VERIFIED**.
- Phase 10.4C: **NOT STARTED**.
- Phase 9.15 / backup / DR: unchanged.

## 8. Checks

| Command | Result |
| --- | --- |
| `git diff --check` | **0** (at commit) |
| Markdown lint | **not configured** |
| Full pytest | **not run** (documentation-only) |

## 9. Explicit non-goals

No application code, migrations, Render apply, staging mutations,
production access, billing changes, processing resume, or Phase 10.4C.
