# Phase 10.4C-A17 — OA-A11-LOGS closure and OA-3 evidence assessment

Documentation-only. Time: **14 Nov 2026, 06:39 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. Evidence assessment only. No
application-code change. No probes, Shell, Environment tab, Trigger
Run, deploy, CONTROL-XWS, OA-3 execution, or Stage B.

OA-5 remains **IN FORCE**. Category A remains **read-only logs
only**. This report does **not** authorize Category B, OA-6, or
Phase 10.4C-B.

APPLICATION CODE CHANGES: **NONE**

## 1. Repository baseline

`git fetch origin main`. Branch created from that SHA.

| Field | Value |
| --- | --- |
| Repository | `https://github.com/mufea/docuflow-ai` |
| Expected prompt SHA | `5ca8867de870a784bf34225e5a15ac01624a4eb8` |
| Actual `origin/main` | `5ca8867de870a784bf34225e5a15ac01624a4eb8` |
| Comparison | **exact match** |
| PR [#110](https://github.com/mufea/docuflow-ai/pull/110) | **MERGED** **13 Nov 2026, 21:19 Asia/Jakarta** |
| A14 | **MERGED** PR #108 `75c789c` |
| A15 fail-fast | **MERGED** PR #109 `5ef9ec8` |
| A15 attribution | **MERGED** PR #110 `5ca8867` |
| A16 report in repo | **NOT AVAILABLE** |
| A17 report | this file (this PR) |
| Live resources contacted | **none** |

A15 attribution `COMPLETE – UNMERGED` on `main` is a stale
**merge-status**. Corrected in `IMPLEMENTATION_STATUS.md` by this
PR. Merge-status correction is not evidence VERIFIED and is not
authorization.

The A17 prompt names “Phase 10.4C-A16 — Post-Remediation Scheduled
Execution Assessment” as the previous milestone. No
`docs/reports/PHASE_10_4C_A16*` file exists on `origin/main`.
Scheduled-run and remediation facts below are taken from this A17
owner prompt, classified as **OWNER-CONFIRMED** / **SUPPORTED**,
not as an independently retrieved Render export.

## 2. Authoritative criteria (unchanged)

OA-A11-LOGS and OA-3 execution criteria remain A11 §3 / §7 / §8
and A12 C1 / C3. No new criteria are invented.

OA-3 (A11): whether the OA-3 cleanup CLI ran successfully **after**
the OA-3-bearing deploy on the **named** cron. Minimum for
**EXECUTION VERIFIED**:

1. Service identity matches the named cron.
2. Deploy SHA **on that service for that Run** is `381b201` or a
   descendant that still contains `e9453bc` (Deploys/header; not
   inferred from GitHub Deployments).
3. Trigger is **Scheduled** (Manual is Category B / supporting).
4. Run start is inside the window (Production: not before ~15:27
   13 Nov 2026 Asia/Jakarta).
5. `docuflow.cleanup` plus `cleanup_cli_ok` **or**
   `cleanup_finished` with `aborted=False`.
6. Not migrate-only.

These are **not** interchangeable: Cron UI SUCCESS, cleanup CLI
success, migrate exit 0, OA-3 completion, runtime isolation.

## 3. Evidence inventory

### C1. Manual Run — 14:02 UTC

Owner-confirmed in this A17 prompt:

| Field | Value |
| --- | --- |
| Environment | Production |
| Service | `docuflow-cleanup` |
| Timestamp | **2026-11-13 14:02:46 UTC** (**21:02:46 Asia/Jakarta**) |
| Trigger | **manual environment-value test** |
| Tokens | `cleanup_cli_ok duration_ms=587`; `cleanup_finished` … `aborted=False` |
| Duplicate finished | copy-paste; not a second Render record |

Classification: **MANUAL SUPPORTING EVIDENCE** /
**OWNER-CONFIRMED**. **Not** Scheduled OA-3 execution proof.
A15 required a Runs row to name service and trigger; the owner has
now named both. That closes the A15 gap **for this Run’s identity
and trigger**. It does **not** convert the Run into Scheduled
proof.

### C2. Secret remediation

Owner-confirmed: `DOCUFLOW_SECRET_KEY` was restored on the
Production cron; owner performed an authorized redeploy/restart.

Classification: **OWNER-CONFIRMED REMEDIATION**. Secret value:
**not** inspected, **not** retrieved, **not** recorded. This agent
did not edit env.

### C3. Post-remediation Scheduled Run

Owner prompt (“existing Render evidence”):

| Field | Reported value | Classification |
| --- | --- | --- |
| Service | `docuflow-cleanup` | **OWNER-CONFIRMED** |
| Environment | Production | **OWNER-CONFIRMED** |
| Deployment SHA (service/chronology) | `5ca8867` | **OWNER-CONFIRMED** (service-level); see SHA row |
| Build started | ~**21:19** Asia/Jakarta | **SUPPORTED** (matches PR #110 merge `14:19:53Z`) |
| Build succeeded / live | ~**21:20** Asia/Jakarta | **SUPPORTED** (chronology) |
| Scheduled start / finish | ~**21:30** / **21:31** Asia/Jakarta | **OWNER-CONFIRMED** |
| Trigger | Scheduled | **OWNER-CONFIRMED** |
| Duration / UI outcome | 53.7 s / SUCCESS | **OWNER-CONFIRMED** |
| Log clock | **2026-11-13 14:31:25 UTC** (**21:31:25 Asia/Jakarta**) | **OWNER-CONFIRMED** |
| `cleanup_cli_ok` / `cleanup_finished` / `aborted=False` | present; `duration_ms=1900`; `storage_failures=0`; `storage_retries=0` | **OWNER-CONFIRMED**; tokens **SOURCE-CONSISTENT** if authentic |
| Logger `name` / JSON envelope | **not stated** for this Run | **NOT AVAILABLE** |
| Exact Run-specific deploy SHA | **not** independently established | **NOT VERIFIED** |

Git: `5ca8867` is a descendant of `381b201` and `e9453bc`
(**VERIFIED** in the repository). That does **not** prove the
Scheduled Run’s header SHA. Do not upgrade by inference.

`5ca8867` is the documentation merge of PR #110. A Render deploy of
that SHA is still a descendant containing OA-3 CLI (`e9453bc`).
Code identity of the tree is **VERIFIED** in git; live Run binding
is **NOT VERIFIED**.

### C4. Pre-remediation failures

| Event | Classification |
| --- | --- |
| A15 JSON `cleanup_config` SECRET_KEY at `13:45:37` (asctime; **20:45** Asia/Jakarta if UTC) | **OWNER-PROVIDED** log line; fail-fast **SOURCE-CONSISTENT** |
| Render Events: cron failed ~**20:57** and ~**21:00** Asia/Jakarta, exit 1 | **OWNER-CONFIRMED** as Events; **cause NOT VERIFIED** (no corresponding log lines in the repo) |
| Subsequent owner remediation | **OWNER-CONFIRMED** |

Do not assume 20:57 / 21:00 were SECRET_KEY fail-fasts without
those logs.

## 4. OA-A11-LOGS acceptance matrix

| Requirement | Evidence | Classification | Result | Gap |
| --- | --- | --- | --- | --- |
| Required log fields (`asctime`, `levelname`, `name`, `message`) | Fail-fast JSON has all four. Success Runs: clocks and tokens, no JSON envelope; scheduled Run omits logger `name` | **PARTIALLY VERIFIED** | Fail-fast envelope **VERIFIED** as pasted; success envelopes **NOT AVAILABLE** | Raw JSON for Scheduled success |
| Production service identity | A17 names `docuflow-cleanup` for Manual and Scheduled | **OWNER-CONFIRMED** | Accept for attribution | Independent dashboard crop **NOT AVAILABLE** |
| Timestamp provenance | Owner UTC clocks; 14:31 UTC ↔ 21:31 WIB | **OWNER-CONFIRMED** | Arithmetic window **VERIFIED** if clocks accepted | Independent Logs export **NOT AVAILABLE** |
| Manual vs Scheduled | 14:02 = Manual; 21:30 = Scheduled | **OWNER-CONFIRMED** | Mandatory split **recorded** | None |
| Scheduled execution evidence | 21:30 Scheduled SUCCESS + tokens | **OWNER-CONFIRMED** / **SUPPORTED** chronology | Present | Run-specific SHA |
| `cleanup_cli_ok` | Manual 587 ms; Scheduled 1900 ms | **OWNER-CONFIRMED**; **SOURCE-CONSISTENT** | Present | Envelope |
| `cleanup_finished` | Both Runs | **OWNER-CONFIRMED**; **SOURCE-CONSISTENT** | Present | Envelope |
| `aborted=False` | Both success Runs | **OWNER-CONFIRMED**; **SOURCE-CONSISTENT** | Present | Envelope |
| Post-remediation evidence | Secret restore + Scheduled after 21:20 live | **OWNER-CONFIRMED** / **SUPPORTED** | Present | Secret not independently viewed (correct) |
| Source attribution | This prompt + prior pasted fail-fast JSON | **OWNER-CONFIRMED** | Agent did not open Render | Independent retrieval **NOT AVAILABLE** |
| Evidence completeness vs A11 §3 | Items 1,3,4,5,6 owner-confirmed for Scheduled; item 2 SHA-on-Run **NOT VERIFIED** | **PARTIALLY VERIFIED** | Cannot close as VERIFIED | SHA on that Run from Deploys/header |

## 5. OA-A11-LOGS closure decision

**B. PARTIALLY VERIFIED** — not **CLOSURE APPROVED BY EVIDENCE**.

Proven: fail-fast JSON fields; git ancestry of `5ca8867`;
documentation merge time of PR #110.

Owner-confirmed: Production `docuflow-cleanup`; Manual 14:02 vs
Scheduled 21:30; success tokens; secret restoration without
exposing the value.

Supported by chronology: build ~21:19 / live ~21:20 / Scheduled
~21:30 after #110 merge.

Unverified: exact Run-specific deployment SHA; JSON envelope and
logger `name` on the Scheduled success log; independent Render
retrieval by this agent; cause of the 20:57 / 21:00 Event failures.

A successful Scheduled cleanup is **not** automatic completion of
every OA-A11-LOGS requirement. A11 §3 item 2 remains open.
Authorization is unchanged. This phase does **not** grant owner
approval beyond Category A already recorded.

## 6. OA-3 assessment (independent)

OA-3 is cleanup-CLI success **after** the OA-3-bearing deploy on
the named cron (A11), not Cron UI SUCCESS, not migrate-only, not
isolation.

| A11 §3 item | Scheduled Run | Result |
| --- | --- | --- |
| 1 Service | OWNER-CONFIRMED `docuflow-cleanup` | **OWNER-CONFIRMED** |
| 2 SHA on the Run | Service-level `5ca8867` OWNER-CONFIRMED; Run-specific **NOT VERIFIED** | **NOT VERIFIED** |
| 3 Scheduled | OWNER-CONFIRMED | **OWNER-CONFIRMED** |
| 4 Window | 21:31 Asia/Jakarta after ~15:27 | **VERIFIED** if UTC clock accepted |
| 5 Success tokens | OWNER-CONFIRMED | **OWNER-CONFIRMED** / **SOURCE-CONSISTENT** |
| 6 Not migrate-only | cleanup tokens present | **OWNER-CONFIRMED** if authentic |

**OA-3: NOT VERIFIED.**

Cron job SUCCESS ≠ cleanup CLI success ≠ migrate completion ≠ OA-3
completion. Manual 14:02 is supporting only. Isolation is out of
scope for OA-3 here.

Minimum missing artifact for OA-3 (no new execution required):
cropped Deploys/header or Runs metadata showing the **21:30
Scheduled** Run’s deploy SHA (`381b201` or descendant containing
`e9453bc`, which `5ca8867` is in git). Optional: one JSON log
object with `name=docuflow.cleanup`.

## 7. Migration command

Blueprint `startCommand`:
`python -m docuflow.migrate && python -m docuflow.cleanup`.

Successful cleanup after `&&` **supports** that migrate exited 0
on that process. It does **not** establish Alembic revision,
schema consistency, pending migrations, or database integrity.
Production DB was **not** inspected. The command is **not**
modified in this PR.

## 8. CONTROL-XWS and runtime isolation

No new isolation evidence. Cron success is not cross-workspace
enforcement. Both remain **NOT VERIFIED**.

## 9. Remaining owner actions

| Missing | Authority | Acceptance | New execution? | Further authorization? |
| --- | --- | --- | --- | --- |
| Run-specific deploy SHA for the **21:30** Scheduled Run | EDY ALAMSAH | Cropped Runs/Deploys showing SHA on that Run | **No** | No (Category A already covers read-only) |
| Optional JSON envelope + `name` for that log | EDY ALAMSAH | One redacted JSON object | **No** | No |

Do not Trigger Run. Do not paste `DOCUFLOW_SECRET_KEY`. Do not
open Environment. Staging cleanup is **not** established by this
Production evidence.

## 10. Status after this assessment

| Item | Status |
| --- | --- |
| Category A | **APPROVED** (read-only cron logs) |
| OA-A11-LOGS | **PARTIALLY VERIFIED** (not closed as VERIFIED) |
| OA-3 | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| Runtime isolation | **NOT VERIFIED** |
| OA-5 | **IN FORCE** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Phase 10.4C | **NOT COMPLETE** |

## 11. Repository CI (this PR)

PR [#111](https://github.com/mufea/docuflow-ai/pull/111) on
`19ef9f2`: **SUCCESS**
[43529121145](https://github.com/mufea/docuflow-ai/actions/runs/43529121145)
(Python `132242129341`, Web `132242129094`; completed
**14 Nov 2026, 06:44 Asia/Jakarta**). Repository CI is not isolation,
not a deploy, and not OA-3 verification.

## 12. Safety declaration

- No Production HTTP probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- Render Environment / Logs / Runs were not opened by this agent.
- No live database connections were made.
- No cleanup operation was executed (including `--dry-run`).
- Cron was not triggered or rescheduled by A17.
- No storage objects were read, written, or deleted.
- No migrations, restore, or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment, Resume, or Suspend was performed by this agent.
- OA-3 was **not** executed by this agent.
- CONTROL-XWS was **not** executed.
- Phase 10.4C-B was not authorized or executed.
- OA-5 was **not** weakened.
- No log evidence was manufactured.
