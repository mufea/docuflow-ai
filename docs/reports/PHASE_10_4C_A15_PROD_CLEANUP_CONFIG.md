# Phase 10.4C-A15 — Production cron `cleanup_config` fail-fast

Documentation-only. Time: **13 Nov 2026, 20:48 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. Owner-provided Production cron log.
No application-code change. No Shell, Environment tab, `--dry-run`,
deploy, database, storage, CONTROL-XWS, or Stage B.

OA-5 remains **IN FORCE**. Category A remains **read-only logs only**.
This report does **not** authorize Category B, env edits, Blueprint
sync, OA-6, or Phase 10.4C-B.

APPLICATION CODE CHANGES: **NONE**

## 1. Repository baseline

`git fetch origin main`. Branch created from that SHA.

| Field | Value |
| --- | --- |
| Repository | `https://github.com/mufea/docuflow-ai` |
| `origin/main` | `75c789c96e2bdb0df209ab2ba6a0621aa655d923` |
| Subject | Merge pull request #108 |
| Commit date | `2026-11-13T13:35:44Z` / **13 Nov 2026, 20:35 Asia/Jakarta** |
| A14 documentation | **MERGED** (PR [#108](https://github.com/mufea/docuflow-ai/pull/108)) |
| Live resources contacted | **none** |

A14 `COMPLETE – UNMERGED` on `main` is now a stale **merge-status**
only. Corrected in `IMPLEMENTATION_STATUS.md` by this PR.

PR [#109](https://github.com/mufea/docuflow-ai/pull/109) head CI on
`c2fc8cb`: **SUCCESS**
[43437066684](https://github.com/mufea/docuflow-ai/actions/runs/43437066684)
(Python `131924816509`, Web `131924816353`; completed **13 Nov 2026,
20:51 Asia/Jakarta**). Repository CI is not isolation and is not a
deploy.

## 2. Owner-provided log (Category A)

Owner: EDY ALAMSAH. Source named: **cron job production**
(`docuflow-cleanup`). One JSON line, pasted in the Cursor agent
conversation at **13 Nov 2026, 20:48 Asia/Jakarta**.

```
{"asctime": "2026-11-13 13:45:37,307", "levelname": "ERROR", "name": "docuflow.cleanup", "message": "cleanup_config DOCUFLOW_SECRET_KEY must be a unique value of at least 32 characters."}
```

No secret value, DSN, or env dump was included. Collection **STOP**
conditions for secrets were **not** hit.

| Field | Recorded value | Notes |
| --- | --- | --- |
| Service | Production cron (`docuflow-cleanup`) | Owner-named; A11 §7 “exactly one” now identifiable |
| `asctime` | `2026-11-13 13:45:37,307` | As written (no zone in JSON). If process clock is UTC: **13 Nov 2026, 20:45:37 Asia/Jakarta** |
| `levelname` | `ERROR` | Matches `logger.error("cleanup_config %s", item)` |
| `name` | `docuflow.cleanup` | Required logger |
| `message` | `cleanup_config DOCUFLOW_SECRET_KEY must be a unique value of at least 32 characters.` | Fail-fast token |
| `cleanup_cli_ok` | **absent** | Success **not** shown |
| `cleanup_finished` / `aborted=False` | **absent** | Success **not** shown |
| Trigger / run id / deploy SHA | **NOT PROVIDED** | Not in this line |
| Window | After Production OA-3 bound ~15:27 13 Nov 2026 Asia/Jakarta | **ACCURATE** if asctime is UTC; **NOT VERIFIABLE** if local TZ is unknown |

## 3. Classification (A11 §8)

| Observation | Classification |
| --- | --- |
| JSON keys `asctime`, `levelname`, `name`, `message` | **COLLECTED** (this line) |
| Token `cleanup_config` | OA-3 **fail-fast ran** |
| `cleanup_cli_ok` / `cleanup_finished` `aborted=False` | **absent** |
| OA-3 successful execution | **NOT VERIFIED** |
| Category A | Remains **APPROVED** (read-only) |
| Category B | **NOT AUTHORIZED** — do not open Shell to “fix” |

A11 §3 weaker evidence: `cleanup_config` then exit 1 means the CLI
refused unsafe config. It is **not** successful cleanup.

OA-A11-LOGS: **PARTIAL** — Production fail-fast line recorded;
success artifacts remain **UNFILLED**.

## 4. Source-backed cause (not a live env read)

`run_cleanup_cli` calls `validate_cleanup_configuration`. When
`settings.is_production`, that function extends
`Settings.production_readiness_errors()`. A weak secret appends
exactly:

`DOCUFLOW_SECRET_KEY must be a unique value of at least 32 characters.`

Weak means: length &lt; 32, a known placeholder in
`_WEAK_SECRET_VALUES` (including the Settings default
`dev-only-change-me-use-32-plus-chars!!`), or a single repeated
character. The default is used when the env var is **unset**.

Production Blueprint `infra/render.yaml` service `docuflow-cleanup`
sets `DOCUFLOW_ENV=production` and copies S3 keys from
`docuflow-api`. It does **not** define `DOCUFLOW_SECRET_KEY`.
`docuflow-api` has `generateValue: true`. The paid worker template
`infra/render.scaling.yaml` copies the API secret via `fromService`;
the cleanup cron does not.

The same omission exists on `docuflow-staging-cleanup`
(`infra/render.staging.yaml`), which also sets
`DOCUFLOW_ENV=production`.

Live Environment values were **not** opened. This explanation is
**SOURCE VERIFIED** for the Blueprint gap and the fail-fast path.
It is **NOT** a dashboard confirmation that the var is unset on
the running cron.

## 5. What this agent did not do

- Did not open Render Environment, Shell, or other services
- Did not edit Production or Staging env
- Did not change `infra/render.yaml` / `infra/render.staging.yaml`
- Did not Trigger Run, Resume, Suspend, or Blueprint sync
- Did not deploy
- Did not weaken `_secret_is_weak` / `production_readiness_errors`
- Did not request or record the secret value
- Did not execute OA-3, CONTROL-XWS, or Phase 10.4C-B

Fail-fast is working as designed. Do not “fix” it by relaxing the
check.

## 6. Remaining owner action

Responsible authority: EDY ALAMSAH.

Missing for OA-3 **EXECUTION VERIFIED**: a later Scheduled run on
`docuflow-cleanup` (and/or staging, separately) whose logs contain
`cleanup_cli_ok` or `cleanup_finished` with `aborted=False`, after
the secret requirement is satisfied.

To satisfy the fail-fast (owner-operated; **not** performed here):

1. Put a unique `DOCUFLOW_SECRET_KEY` of at least 32 characters on
   `docuflow-cleanup`. Preferred: copy from `docuflow-api` via
   Render `fromService` (same pattern as `infra/render.scaling.yaml`).
   Do **not** paste the value into chat, tickets, or this repository.
2. Persist the same mapping in the Blueprint **only** if the owner
   authorizes a configuration change and the subsequent cron deploy.
   This phase does **not** authorize that.
3. Do **not** Trigger Run unless Category B is separately approved.
   Wait for the next `*/15 * * * *` Scheduled run.
4. Collect the success tokens under Category A. If a further
   `cleanup_config` line appears, record it; do not open Shell.

Staging has the same Blueprint omission. Do not assume Staging
cleanup succeeded.

Env edit and Blueprint deploy remain **Category B / DEPLOY** and
are **NOT AUTHORIZED** for this agent.

## 7. Status after this record

| Item | Status |
| --- | --- |
| Category A | **APPROVED** (read-only cron logs) |
| OA-A11-LOGS | **PARTIAL** (Production fail-fast line; success **UNFILLED**) |
| OA-3 execution | **NOT VERIFIED** (fail-fast ran) |
| CONTROL-XWS | **NOT VERIFIED** |
| Runtime isolation | **NOT VERIFIED** |
| OA-5 | **IN FORCE** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Phase 10.4C | **NOT COMPLETE** |

## 8. Safety declaration

- No Production HTTP probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- Render Environment was not opened.
- No live database connections were made.
- No cleanup operation was executed (including `--dry-run`).
- Cron was not triggered or rescheduled.
- No storage objects were read, written, or deleted.
- No migrations, restore, or export operations were performed.
- No credentials or DSNs were exposed. The owner log line contained
  none.
- No infrastructure or application configuration was changed.
- No deployment, Resume, or Suspend was performed.
- OA-3 was **not** executed by this agent (the cron ran on Render;
  this agent did not invoke it).
- CONTROL-XWS was **not** executed.
- Phase 10.4C-B was not authorized or executed.
- OA-5 was **not** weakened.
- Secret validation was **not** relaxed.
- No success log was manufactured.
