# Phase 10.4C-A11 — Owner-gated OA-3 verification readiness

Documentation-only planning. Time: **13 Nov 2026, 17:06 Asia/Jakarta
(WIB)**. Owner / Approver: EDY ALAMSAH. No application-code change.
No Render logs, Shell, cleanup (including `--dry-run`), deploy,
database, storage, env inspection, or Stage B.

OA-5 remains **IN FORCE**. This report is a **plan**. It does **not**
inspect logs. It does **not** grant Category A or Category B
approval. A merged PR, CI SUCCESS, this document, and a generic
“continue” are **not** authorization.

APPLICATION CODE CHANGES: **NONE**

## 1. Current Git baseline

`git fetch origin main`. Branch created from that SHA.

| Field | Value |
| --- | --- |
| `origin/main` | `1cdf250b8206973865ee14d8b4a099375e6522e1` |
| Subject | Merge pull request #103 |
| Commit date | `2026-11-13T16:44:50+07:00` / **13 Nov 2026, 16:44 Asia/Jakarta** |
| Merged by | `mufea` |
| Inspector | Cursor Agent (this workspace) |
| Live resources contacted | **none** |

| PR | Role | Status | Merge SHA | Merged (Asia/Jakarta) |
| --- | --- | --- | --- | --- |
| [#97](https://github.com/mufea/docuflow-ai/pull/97) | OA-2 helper | **MERGED** | `cf0d615` | **13:56** |
| [#98](https://github.com/mufea/docuflow-ai/pull/98) | OA-3 CLI | **MERGED** | `e9453bc` | **14:08** |
| [#102](https://github.com/mufea/docuflow-ai/pull/102) | A8R evidence | **MERGED** | `4772eb1` | **15:41** |
| [#103](https://github.com/mufea/docuflow-ai/pull/103) | A10 recon | **MERGED** | `1cdf250` | **16:44** |

PR #103 head `467ae37` is an ancestor of `1cdf250`. Owner-recorded
repository CI on `467ae37`: **SUCCESS**
[43403099428](https://github.com/mufea/docuflow-ai/actions/runs/43403099428)
(**13 Nov 2026, 16:40 Asia/Jakarta**). Repository CI is not runtime
verification.

PR [#104](https://github.com/mufea/docuflow-ai/pull/104) head CI on
`16b55c2`: **SUCCESS**
[43406797445](https://github.com/mufea/docuflow-ai/actions/runs/43406797445)
(Python `131822978255`, Web `131822978685`; completed **13 Nov 2026,
17:09 Asia/Jakarta**). Repository CI is not isolation and is not a
deploy.

Carried classifications (unchanged):

| Item | Status |
| --- | --- |
| Cleanup deploy SHA (both crons) | OWNER-PROVIDED **`381b201`** (**DEPLOYMENT EVIDENCE PROVIDED**) |
| OA-3 successful post-change execution | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| Overall runtime isolation | **NOT VERIFIED** |
| OA-5 | **IN FORCE** (PR #99 `06ba141`) |
| OA-6 / Phase 10.4C-B | **NOT AUTHORIZED** |
| Phase 10.4C | **NOT COMPLETE** |

A10 **COMPLETE – UNMERGED** on `origin/main` is stale; git status is
**MERGED** `1cdf250`. Corrected in `IMPLEMENTATION_STATUS.md` by this
PR. A10 Track A remains a sketch; this report is the Category A
procedure and approval template.

## 2. Relevant source and logging behavior

Inspected (read-only, repository): `src/docuflow/cleanup.py`,
`src/docuflow/jobs/scheduler.py`, `src/docuflow/jobs/retention.py`,
`src/docuflow/jobs/leases.py`, `src/docuflow/logging.py`,
`src/docuflow/migrate.py`, `infra/render.yaml`,
`infra/render.staging.yaml`, `tests/test_phase104c_cleanup_cli.py`.

Cron identity (Blueprint `name`):

| Environment | Service | Schedule | startCommand |
| --- | --- | --- | --- |
| Staging | `docuflow-staging-cleanup` | `*/15 * * * *` | `python -m docuflow.migrate && python -m docuflow.cleanup` |
| Production | `docuflow-cleanup` | `*/15 * * * *` | same |

The cron does **not** pass `--dry-run`. The in-process
`CleanupScheduler` (API/worker) is a **different** entry point and is
**out of scope** for this OA-3 cron plan.

Logger: `logging.getLogger("docuflow.cleanup")`. Cron env sets
`LOG_JSON=true` and `DOCUFLOW_ENV=production`, so
`configure_logging` uses `JsonFormatter` with format
`%(asctime)s %(levelname)s %(name)s %(message)s`. Configured JSON
keys: **`asctime`**, **`levelname`**, **`name`**, **`message`**.
Other formatter keys: **NOT VERIFIED** (no sample log collected).

Application execution / correlation ID: **UNAVAILABLE**. The lease
token is `uuid.uuid4().hex` in `run_runtime_cleanup` and is **not**
logged. Source does **not** log git SHA, Render run id, or
`RENDER_SERVICE_NAME`.

Logged message tokens (exact strings in source):

| Token | Logger | Meaning |
| --- | --- | --- |
| `cleanup_config` | error | Fail-fast; CLI then exits 1 |
| `cleanup_cli_ok duration_ms=` | info | CLI finished `run_runtime_cleanup` (not skipped) |
| `cleanup_cli_skipped` | info | CLI; lease held; process still exits 0 |
| `cleanup_cli_dry_run backend= bucket=` | info | `--dry-run` only; **not** expected on cron |
| `cleanup_finished ... duration_ms= aborted=` | info | Body completed (may be `aborted=True`) |
| `cleanup_skipped reason=lease_held` | info | Body skipped |
| `cleanup_aborted reason=lease_lost` | warning | Partial abort |
| `cleanup_lease_acquired name=` | info | Lease name is `runtime` |
| `cleanup_lease_release_failed` | exception | Release failed |
| `alembic_upgrade_locked` / `alembic_upgrade_unlocked` | `docuflow.migrate` | **Migrate** prefix of startCommand, not cleanup success |

`CleanupScheduler` tokens (`cleanup_scheduler_started`,
`cleanup_scheduler_refused`, `cleanup_loop_failed`) apply to
API/worker, **not** these cron jobs.

## 3. Minimum evidence required

Target: one named cron service, one time window **after** that
service’s OA-3-bearing deploy.

| Service | Window start (Asia/Jakarta, OWNER-PROVIDED deploy) | SHA in window |
| --- | --- | --- |
| `docuflow-staging-cleanup` | **not before ~15:17** 13 Nov 2026 (Auto-Deploy `381b201`); optional earlier bound ~14:32 for Auto-Deploy `e9453bc` | `381b201` or descendant that still contains #98 |
| `docuflow-cleanup` | **not before ~15:27** 13 Nov 2026 (**Resumed** `381b201`) | same |

Last OWNER-PROVIDED green Runs (Staging **14:00** 13 Nov; Production
**16:30** 10 Nov) are **before** those windows and **do not** count.

Minimum for **EXECUTION VERIFIED** (successful OA-3 cron body):

1. Service identity matches the named cron.
2. Deploy SHA on that service for the Run is `381b201` or a
   descendant that includes `e9453bc` (OWNER-PROVIDED Deploys/header,
   not inferred from GitHub Deployments — cleanup has **none**).
3. Run trigger is **Scheduled** (or owner-named Manual, which is
   still Category B if the owner triggered it during the inspection).
4. Run start is **inside** the window.
5. Redacted log contains `name=docuflow.cleanup` (or equivalent JSON
   `name`) and `cleanup_cli_ok` **or** `cleanup_finished` with
   `aborted=False` / `aborted=false`.
6. Process is not only migrate: `alembic_upgrade_*` alone is
   **insufficient**.

Weaker supporting evidence (not by itself **EXECUTION VERIFIED**):

- Green Runs-tab row after the window, SHA still `381b201`, **no**
  logs: **DEPLOYMENT EVIDENCE PROVIDED** + UI success; OA-3 body
  still **NOT VERIFIED**.
- `cleanup_config` then exit 1: OA-3 **fail-fast ran**; successful
  cleanup **NOT VERIFIED**.
- `cleanup_cli_skipped` / `cleanup_skipped reason=lease_held`:
  validator passed; body skipped; successful cleanup **NOT VERIFIED**.

## 4. Category A — Read-only evidence inspection (future only)

**NOT AUTHORIZED** until the owner fills §7 and names this category
explicitly. Later: Category A was **APPROVED** for read-only cron
logs only — see
`docs/reports/PHASE_10_4C_A14_CATEGORY_A_APPROVAL.md`. Log
artifacts remain **UNFILLED**. Category B remains **NOT AUTHORIZED**.

Permitted **after** that APPROVE, and only for the named service and
window:

1. Open that cron’s **Logs** (and optionally a cropped **Runs** row)
   for the window. Do **not** open Environment, Shell, or other
   services.
2. Find one Run whose start is in the window.
3. Record: service name, trigger (Scheduled vs Manual vs deploy),
   start time (Asia/Jakarta), duration if shown, exit/success if
   shown, deploy SHA from header/Deploys (already OWNER-PROVIDED
   `381b201` unless a newer owner capture exists).
4. From logs, copy **only** allowed markers in §3 / §7. Redact per
   §6.
5. Classify per §8. Stop on §8 conditions.
6. Do not Trigger Run, do not scroll into env values, do not follow
   links into other resources.

Render UI run identifiers: **not defined in repository source**. If
the dashboard shows a run id, the owner may include a cropped id
**without** treating a guessed field name as SOURCE VERIFIED.

## 5. Category B — Prohibited mutating / operational actions

**NOT AUTHORIZED.** Category A approval **never** implies Category B.

- Trigger Run / reschedule cron
- `python -m docuflow.cleanup` or `docuflow-cleanup`
- `--dry-run` against live Staging or Production
- Render Shell / SSH
- Deploy, Resume, Suspend, Blueprint sync
- Env var view or edit
- SQL, Redis, R2, HeadBucket, ListObjects
- Migrate, backup, restore, export
- CONTROL-XWS probes
- Phase 10.4C-B / OA-6

`cleanup_cli_dry_run` in a live log would mean `--dry-run` was
invoked; that is Category B evidence, not Category A cron evidence.

## 6. Redaction requirements

Do **not** record:

- `DATABASE_URL`, DSN, user, password
- `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, tokens, cookies
- Redis URLs, signed URLs, `x-amz-*`
- Full object keys / customer document names if present
- Private hostnames beyond already-public Render service names

`configure_logging` redacts selected dict keys via `redact()`; CLI
messages are **plain strings** and are **not** automatically
redacted. `cleanup_cli_dry_run` includes `bucket=`. Bucket names may
be operational; still omit if the owner forbids them. Prefer message
**tokens** (`cleanup_cli_ok`) over full lines when a line contains
`=` values.

If a secret appears: **stop**, do not paste, do not screenshot the
secret region.

## 7. Owner approval template (unfilled)

Do **not** treat this block as an approval. Values must be filled by
EDY ALAMSAH in a later message.

```
OA-A11-LOGS — Category A read-only log inspection
Status: NOT APPROVED

Approver:
Date (Asia/Jakarta):
Expires at (Asia/Jakarta):

Target service (exactly one per approval):
  [ ] docuflow-staging-cleanup
  [ ] docuflow-cleanup

Action (this approval grants ONLY):
  [ ] Read-only logs inspection of the named cron
  [ ] Optional cropped Runs row for the same Run (no Trigger Run)

Time window (Asia/Jakarta):
  Start:
  End:

Purpose:
  Determine whether OA-3 cleanup CLI ran successfully after the
  OA-3-bearing deploy SHA on the named service.

Permitted evidence fields:
  - Service name
  - Deploy SHA shown on that service
  - Run trigger (Scheduled / Manual / other as labeled)
  - Run start/end or duration as shown
  - Log logger name `docuflow.cleanup`
  - Message tokens listed in PHASE_10_4C_A11 §2
  - JSON keys asctime, levelname, name, message

Prohibited data:
  - Credentials, DSNs, tokens, env values
  - Shell, Trigger Run, --dry-run, deploy/resume
  - Other services, databases, object storage

Stop conditions:
  - Secret/DSN/token visible
  - Window or service mismatch
  - Approval expired
  - Any Category B action would be required to continue

Category B: NOT IMPLIED
Phase 10.4C-B: NOT IMPLIED
OA-5: remains IN FORCE except this named Category A window
```

Later record (do **not** treat the block above as filled): Category A
was **APPROVED** by EDY ALAMSAH in a later owner message (conversation
clock **13 Nov 2026, 20:20 Asia/Jakarta**; re-confirmed **20:30** with
written date **13 Nov 2026, 20:20**; earlier 2027 write superseded)
for read-only Render cron log inspection only. See
`docs/reports/PHASE_10_4C_A14_CATEGORY_A_APPROVAL.md`. Log artifacts
remain **UNFILLED**. This §7 template is not rewritten.

## 8. Failure and stop conditions

| Observation | Classification | Action |
| --- | --- | --- |
| No Run in window | **NOT VERIFIED** | Stop; do not Trigger Run |
| Green UI Run, no logs | UI success only; **EXECUTION VERIFIED** still **NOT VERIFIED** | Stop or wait for log APPROVE |
| Logs missing / truncated | **NOT VERIFIED** / incomplete | Do not reconstruct |
| Ambiguous (migrate only; no `docuflow.cleanup`) | **NOT VERIFIED** | Do not upgrade |
| `cleanup_config` / exit 1 | Fail-fast ran; success **NOT VERIFIED** | Do not open Shell to “fix” |
| `cleanup_cli_ok` or `cleanup_finished` `aborted=False` in window | Candidate **EXECUTION VERIFIED** (record, do not start Stage B) | Redact and stop |
| Secret in view | **STOP** | No paste |
| Approval expired / wrong service | **STOP** | |

Do not diagnose red Runs as OA-3 fail-fast without the
`cleanup_config` token.

## 9. Outstanding evidence gaps

1. OA-3 successful post-change execution: **NOT VERIFIED**.
   Later owner log (A15 fail-fast): Production `cleanup_config` on
   `DOCUFLOW_SECRET_KEY`. Later owner excerpt (A15 attribution):
   `cleanup_cli_ok` / `cleanup_finished aborted=False` at
   **2026-11-13 14:02:46.536 UTC** — OWNER-ASSERTED; not independently
   bound to `docuflow-cleanup` + SHA-on-Run + Scheduled trigger.
2. Application execution id: **UNAVAILABLE**.
3. Git SHA inside cleanup logs: **UNAVAILABLE**.
4. Cleanup GitHub Deployments: **none**.
5. Post-#102/#103 cleanup SHA (whether still `381b201`): **NOT VERIFIED**.
6. CONTROL-XWS: **NOT VERIFIED**.
7. Category A: **NOT APPROVED** at A11 time. Later: **APPROVED**
   (read-only cron logs only) — see A14.
8. Phase 10.4C-B: **NOT AUTHORIZED**.

## 10. Safety declaration

- No Production probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- Render logs were not opened.
- No live database connections were made.
- No cleanup operation was executed (including `--dry-run`).
- No storage objects were read, written, or deleted.
- No migrations were executed.
- No restore or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment, Resume, or Suspend was performed.
- Cron was not triggered or rescheduled.
- Phase 10.4C-B was not authorized or executed.
- Category A was planned only; it was **not** approved or executed.
