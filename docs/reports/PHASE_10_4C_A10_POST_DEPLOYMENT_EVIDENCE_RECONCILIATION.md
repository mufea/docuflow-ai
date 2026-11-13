# Phase 10.4C-A10 — Post-deployment evidence reconciliation

Documentation-only. Time: **13 Nov 2026, 16:36 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. No application-code change. No
Blueprint, env, deploy, migrate, cleanup (including `--dry-run`),
object I/O, Render Shell, logs, Production or Staging probe, or
Stage B.

OA-5 remains **IN FORCE**. MERGED is **not** DEPLOYED. A deployment
SHA is **not** a successful execution. CI SUCCESS is **not**
isolation. Distinct Render workspaces are **not** CONTROL-XWS.
This phase does **not** authorize Phase 10.4C-B.

## 1. Audit scope and timestamp

Reconcile git and GitHub metadata after PR #102 merged, check
that owner-supplied cleanup Deploys/Runs evidence is already on
`main`, correct the stale A8R **COMPLETE – UNMERGED** ledger, and
record owner-gated next-step tracks **without executing them**.

APPLICATION CODE CHANGES: **NONE**

Live resources contacted: **none**. Render dashboard opened by
this agent: **no**.

## 2. Git baseline

`git fetch origin main`. Branch created from that SHA.

| Field | Value |
| --- | --- |
| `origin/main` HEAD | `4772eb1954848987449e4cd249d13e8d9f22f924` |
| Subject | Merge pull request #102 |
| Commit date | `2026-11-13T15:41:56+07:00` / **13 Nov 2026, 15:41 Asia/Jakarta** |
| Merged by | `mufea` |
| Inspector | Cursor Agent (this workspace) |

Ancestor checks (all **yes**):

- PR #97 merge `cf0d615c476b43c1247876835d03482ecb7de2b9`
- PR #98 merge `e9453bc1436a66459d4ba6eab954ef5c70624392`
- PR #101 merge `381b20191c0fbab78b39eb309f3e8c37d2ebecf8`
- PR #102 head `252e6d20717484c6dbb9ac8c62ce9ceec7194b5e`

`381b201` is an **ancestor** of current `origin/main`, not the
current HEAD. `git diff 381b201 origin/main` is **docs only**
(`docs/IMPLEMENTATION_STATUS.md` and
`docs/reports/PHASE_10_4C_A8R_CLEANUP_OWNER_EVIDENCE.md`). `src/`,
`tests/`, and `infra/` are identical between those SHAs.

## 3. PR #97 / #98 / #102 reconciliation

| PR | Role | GitHub | Merge SHA | Merged (Asia/Jakarta) | On `origin/main` |
| --- | --- | --- | --- | --- | --- |
| [#97](https://github.com/mufea/docuflow-ai/pull/97) | OA-2 Production bucket helper | **MERGED** | `cf0d615` | **13:56** | **yes** |
| [#98](https://github.com/mufea/docuflow-ai/pull/98) | OA-3 cleanup CLI safety | **MERGED** | `e9453bc` | **14:08** | **yes** |
| [#102](https://github.com/mufea/docuflow-ai/pull/102) | A8R owner cleanup evidence (docs) | **MERGED** | `4772eb1` | **15:41** | **yes** (HEAD) |

Source on `origin/main` (**SOURCE VERIFIED**):

- `DEFAULT_PRODUCTION_BUCKETS = {"docuflow-documents", "docuflowai-documents"}` in `src/docuflow/staging_checks.py`.
- Cleanup CLI fail-fast (`CleanupConfigError` before engine/session/storage), empty `S3_BUCKET` refuse, Production-bucket refuse only when `cleanup_context_is_isolated()`, `--dry-run` validates and exits.
- `CleanupScheduler.run_once` shares `validate_cleanup_configuration`.
- Blueprint cron names unchanged: Staging `docuflow-staging-cleanup`, Production `docuflow-cleanup`; startCommand `python -m docuflow.migrate && python -m docuflow.cleanup` every 15 minutes.
- Production cron with a Production bucket may still clean `docuflowai-documents`.

Local targeted tests (**TEST VERIFIED**, SQLite, no live resources):

```
DOCUFLOW_ENV=test DATABASE_URL=sqlite:///:memory: uv run pytest tests/test_phase104c_cleanup_cli.py tests/test_phase91_cleanup.py -q
# 20 passed in 1.41s
```

Repository CI on `main` after #102 (**CI VERIFIED**; not isolation;
not a cleanup deploy):

- [43395258245](https://github.com/mufea/docuflow-ai/actions/runs/43395258245) **SUCCESS**
- Python `131784512542`, Web `131784512806`
- Completed **13 Nov 2026, 15:44 Asia/Jakarta**

A8R evidence documentation is already on `main` (PR #102). This
pass does **not** duplicate screenshots. It reconciles git status
and classification.

Stale ledger on `origin/main` before this PR: A8R still said
**COMPLETE – UNMERGED**. Git status is **MERGED** `4772eb1`.

## 4. Staging cleanup — `docuflow-staging-cleanup`

OWNER-PROVIDED (A8R Runs/Deploys; restated by owner for this
phase). Agent did **not** open Render.

| Field | Record |
| --- | --- |
| Service identity (Blueprint / A8R UI) | `docuflow-staging-cleanup` (cron) |
| Owner-reported SHA | `381b201` |
| Trigger | **Auto-Deploy** |
| Owner-reported time | ~**15:17 Asia/Jakarta** (15m before 15:32 clock) |
| Also reported Auto-Deploy rows | `#97` `cf0d615`, `#98` `e9453bc`, `#101` `381b201` |
| Last successful cron (OWNER-PROVIDED) | **13 Nov 2026, 14:00 Asia/Jakarta** |
| After OA-3 merge 14:08? | **no** |
| GitHub Deployments for this cron | **none** (environments: api/web/staging-api/staging-web; historical db/worker) |
| Current SHA after #102 (15:41) | **NOT VERIFIED** (no owner capture after 15:32) |

Classification:

- Commit inclusion of #97/#98 **in reported SHA `381b201`**: git **yes**
- Cleanup deploy event: **DEPLOYMENT EVIDENCE PROVIDED** (OWNER-PROVIDED)
- Independent **DEPLOYMENT VERIFIED**: **NOT VERIFIED**
- **EXECUTION VERIFIED** (OA-3): **NOT VERIFIED**

A8R labeled this **VERIFIED (OWNER-PROVIDED)**. This phase uses the
stricter A10 taxonomy: owner dashboard evidence is
**DEPLOYMENT EVIDENCE PROVIDED**, not independently
**DEPLOYMENT VERIFIED**. The screenshots are not withdrawn.

## 5. Production cleanup — `docuflow-cleanup`

OWNER-PROVIDED. Agent did **not** open Render.

| Field | Record |
| --- | --- |
| Service identity | `docuflow-cleanup` (cron) |
| Owner-reported SHA | `381b201` |
| Trigger | **Resumed** (not a new Auto-Deploy of #97 or #98) |
| Owner-reported time | ~**15:27 Asia/Jakarta** (5m before 15:32 clock) |
| Previous Deploys row | PR `#44` `bed6140` Auto-Deploy ~2d earlier |
| Separate `#97` / `#98` Production rows | **none reported**; do **not** infer them |
| #97/#98 inclusion | git ancestry of `381b201` only |
| Last successful cron (OWNER-PROVIDED) | **10 Nov 2026, 16:30 Asia/Jakarta** |
| After OA-3? | **no** |
| GitHub Deployments for this cron | **none** |
| Current SHA after #102 (15:41) | **NOT VERIFIED** |

**Resumed** is a resume-from-suspended event onto `381b201`. It is
not an Auto-Deploy of #97 or #98. It is not owner authorization to
run live cleanup. A3 historically recorded this service as
**Suspended**.

Classification:

- Cleanup deploy event: **DEPLOYMENT EVIDENCE PROVIDED** (OWNER-PROVIDED)
- Independent **DEPLOYMENT VERIFIED**: **NOT VERIFIED**
- **EXECUTION VERIFIED** (OA-3): **NOT VERIFIED**

## 6. Cron execution timeline

All times Asia/Jakarta.

| Event | Time | Source |
| --- | --- | --- |
| OA-2 merge #97 `cf0d615` | **13:56** 13 Nov 2026 | GitHub |
| Staging last **successful** cron | **14:00** 13 Nov 2026 | OWNER-PROVIDED Runs |
| OA-3 merge #98 `e9453bc` | **14:08** 13 Nov 2026 | GitHub |
| Staging Auto-Deploy `#97`/`#98` (approx.) | **~14:32** | OWNER-PROVIDED Deploys (1h before 15:32) |
| Staging Auto-Deploy `#101` `381b201` | **~15:17** | OWNER-PROVIDED Deploys |
| Production **Resumed** `381b201` | **~15:27** | OWNER-PROVIDED Deploys |
| Production last **successful** cron | **16:30** **10 Nov 2026** | OWNER-PROVIDED Runs |
| A8R Deploys screenshots | **15:32** 13 Nov 2026 | OWNER-PROVIDED |
| PR #102 merge `4772eb1` | **15:41** 13 Nov 2026 | GitHub |

Staging last success is **after** OA-2 and **before** OA-3. Later
Staging scheduled Runs were red; Production Manual ~15:26 failed.
Failure cause: **NOT VERIFIED** (logs not opened; OA-5). Do **not**
treat red Runs as diagnosed OA-3 fail-fast.

## 7. OA-3 execution verification gap

OA-3 successful execution remains **NOT VERIFIED** because:

1. Last green Staging run (**14:00**) predates OA-3 merge (**14:08**).
2. Last green Production run (**10 Nov 2026, 16:30**) predates both OA-2 and OA-3.
3. Later visible Runs failed; logs were not opened.
4. A deploy SHA (even OWNER-PROVIDED `381b201`) does not prove a
   successful cron of that SHA.
5. `--dry-run` and live cleanup were **not** executed this phase.

Minimum evidence that would be required later (not collected now):

- Explicit owner APPROVE naming the **target service**,
  **read-only vs mutating**, **exact operation**, **scope/time
  window**, whether **cleanup execution is allowed**, expected
  artifact, and **stop conditions**.
- A green Run whose start time is **after** the OA-3-bearing deploy
  on that same service, **or** a redacted log line proving
  `cleanup_cli_ok` / validated `--dry-run` on that SHA.
- A read-only log review **must not** be treated as cleanup
  execution approval.

## 8. Evidence classification matrix

| Item | Classification |
| --- | --- |
| PR #97 / #98 / #102 | **MERGED** |
| OA-2 / OA-3 source on `origin/main` | **SOURCE VERIFIED** |
| Targeted cleanup unit tests | **TEST VERIFIED** (20 passed) |
| `main` CI after #102 | **CI VERIFIED** (not isolation) |
| Staging/Production API/web SHA `4772eb1` | **DEPLOYMENT VERIFIED** (GitHub Render App success `7761006389` / `7761006442` / `7761006496` / `7761006467` at **15:41**; `production_environment: true` is also set on Staging records and is **not** Production proof) |
| Staging/Production cleanup SHA `381b201` | **DEPLOYMENT EVIDENCE PROVIDED** (OWNER-PROVIDED Deploys 15:32) |
| Cleanup SHA independently via GitHub Deployments | **NOT VERIFIED** (no cron environments) |
| Cleanup SHA after #102 `4772eb1` | **NOT VERIFIED** |
| Successful OA-3 cron | **NOT VERIFIED** / not **EXECUTION VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| Overall runtime isolation | **NOT VERIFIED** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Live cleanup / logs / Shell | **NOT AUTHORIZED** |
| OA-5 | **IN FORCE** |

GitHub API/web deploy of `4772eb1` includes #97/#98 by ancestry.
That does **not** prove cleanup cron identity or a cleanup run.

## 9. Outstanding isolation and security gaps

Unchanged from OA-1 / A3 / A8R:

1. CONTROL-XWS: Staging process must not be shown to read Production
   `DATABASE_URL` or Production `S3_BUCKET`. Distinct workspaces
   (`docuflowai` vs `docuflowai staging`) are not that proof.
2. Isolation is env injection, not an application allow-list.
3. Production cleanup may still target `docuflowai-documents` when
   context is not isolated.
4. Cron failure cause unknown without logs (OA-5).
5. Phase 10.4C-B remains **NOT AUTHORIZED**.

## 10. Owner-gated next actions (plan only)

Do **not** execute. OA-5 stays **IN FORCE** until a **named**
APPROVE for a specific action. Merged PRs, CI SUCCESS, this
document, and a generic “continue” are **not** approval.

### Track A — OA-3 post-change execution verification

**NOT AUTHORIZED.**

Any future APPROVE must name:

| Required field | Constraint |
| --- | --- |
| Target service | `docuflow-staging-cleanup` and/or `docuflow-cleanup` |
| Read-only vs mutating | Log review is read-only; `--dry-run` and cron Trigger Run are **not** log review |
| Exact operation | e.g. cropped Runs row after `381b201`/`4772eb1`; or redacted log lines; or `--dry-run` in Shell |
| Scope and time window | Service + SHA + start/end |
| Cleanup execution allowed? | Default **no** |
| Expected evidence | Green Run after OA-3 deploy, or redacted `cleanup_cli_ok` / dry-run log |
| Stop conditions | Secret/DSN in view → stop; unexpected Production bucket in Staging → stop |

Read-only log review **does not** imply `--dry-run` or mutating
cleanup.

### Track B — CONTROL-XWS isolation verification

**NOT AUTHORIZED.** Residual from OA-1 Option A.

Closing this gap would require a **separately approved** negative
test that Staging cannot use Production database or bucket
credentials. This phase does **not** request credentials, DSNs, or
probes.

### Track C — Phase 10.4C-B

**NOT AUTHORIZED.** OA-6 remains **NOT APPROVED**.

Prerequisites before any future Stage B (none of these are
approvals):

- Owner names Stage B explicitly (OA-6).
- OA-5 still respected unless a named exception is granted.
- Track A does not by itself start Stage B.
- CONTROL-XWS remaining **NOT VERIFIED** must stay visible; OA-1
  accepted that residual and did not convert isolation to PASS.

## 11. Safety declaration

- No Production probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- No live database connections were made.
- No cleanup operation was executed by this agent (including
  `--dry-run` against live services).
- No storage objects were read, written, or deleted.
- No migrations were executed.
- No restore or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment, Resume, or Suspend was performed.
- Render dashboards were not opened by this agent.
- Cron was not triggered or rescheduled.
- Phase 10.4C-B was not authorized or executed.
