# Phase 10.4C-A15 — OA-A11-LOGS evidence attribution

Documentation-only. Time: **13 Nov 2026, 21:16 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. Owner prompt title matches this
assessment. The earlier A15 fail-fast record (PR
[#109](https://github.com/mufea/docuflow-ai/pull/109)) remains a
separate ledger row. No application-code change. No probes, Shell,
Environment tab, Trigger Run, deploy, CONTROL-XWS, OA-3 execution,
or Stage B.

OA-5 remains **IN FORCE**. Category A remains **read-only logs
only**. This report does **not** authorize Category B, OA-6, or
Phase 10.4C-B.

APPLICATION CODE CHANGES: **NONE**

## 1. Repository baseline

`git fetch origin main`. Branch created from that SHA.

| Field | Value |
| --- | --- |
| Repository | `https://github.com/mufea/docuflow-ai` |
| Expected prompt baseline | `75c789c96e2bdb0df209ab2ba6a0621aa655d923` (PR #108) |
| Actual `origin/main` | `5ef9ec875287b562d7d46b40577bd3af6754079c` |
| Difference | PR [#109](https://github.com/mufea/docuflow-ai/pull/109) **MERGED** after #108 (**13 Nov 2026, 20:54 Asia/Jakarta**) |
| A14 | **MERGED** PR #108 `75c789c` |
| A15 fail-fast docs | **MERGED** PR #109 `5ef9ec8` |
| `381b201` vs `main` | **ancestor** (SOURCE VERIFIED in git; not a live cron SHA) |
| Live resources contacted | **none** |

The SHA difference is explained. Work continues from actual
`origin/main`. A15 fail-fast `COMPLETE – UNMERGED` on `main` is a
stale **merge-status** only. Corrected in
`IMPLEMENTATION_STATUS.md` by this PR.

## 2. Supplied excerpt (as received)

Owner: EDY ALAMSAH. Conversation **13 Nov 2026, 21:16 Asia/Jakarta**.

| Field | Owner text |
| --- | --- |
| Timestamp | `2026-11-13 14:02:46.536 UTC` |
| Environment | Production |
| Logger | `docuflow.cleanup` |
| Level | INFO |
| Events | `cleanup_cli_ok duration_ms=587` ; `cleanup_finished abandoned_jobs=0 refunded_credits=0 expired_documents=0 storage_deleted=0 storage_failures=0 storage_retries=0 duration_ms=587 aborted=False` |
| Duplicate `cleanup_finished` | Owner: copy-paste; **not** a second Render record |
| Deployment reference | `381b201` |

No raw JSON object was pasted. No secret, DSN, or env dump.

Prior A15 fail-fast line (`asctime` `2026-11-13 13:45:37,307`,
`cleanup_config` SECRET_KEY) is a **separate** record. It is not
this excerpt.

## 3. Content validity

| Required item | In excerpt? | Source check | Classification |
| --- | --- | --- | --- |
| `asctime` JSON key | **No** (clock given as `2026-11-13 14:02:46.536 UTC`) | Prior fail-fast used `asctime` with comma-ms and no zone | **OWNER-ASSERTED** |
| `levelname` JSON key | **No** (stated INFO) | `cleanup_cli_ok` / `cleanup_finished` are `logger.info` | **OWNER-ASSERTED** |
| `name` JSON key | **No** (stated `docuflow.cleanup`) | Required logger in A11 §2 | **OWNER-ASSERTED** |
| `message` JSON key | **No** (event strings only) | Tokens match source format below | **OWNER-ASSERTED** envelope; tokens **SOURCE-CONSISTENT** |
| `cleanup_cli_ok` | **Yes** `duration_ms=587` | `cleanup.py`: `cleanup_cli_ok duration_ms=%s` | **SOURCE-CONSISTENT** |
| `cleanup_finished` field list | **Yes**, same order as `retention.py` | Exact format string | **SOURCE-CONSISTENT** |
| `aborted=False` | **Yes** | `%s` of bool → `False` | **SOURCE-CONSISTENT** |
| Same `duration_ms=587` on both tokens | **Yes** | CLI logs the same `stats.duration_ms` after the body | **SOURCE-CONSISTENT** (not Render metadata) |

A11 required JSON keys are **not** independently present. Event
strings match repository source. Content is **PARTIALLY VERIFIED**
(tokens) / **OWNER-ASSERTED** (envelope, clock, logger, level).

Duplicate `cleanup_finished`: **OWNER-ASSERTED** copy-paste. This
assessment treats **one** finished event, not two Runs.

## 4. Source attribution

| Item | Classification | Note |
| --- | --- | --- |
| Production environment | **OWNER-ASSERTED** | Stated in the prompt; not a Render resource id |
| Cron service identity | **NOT AVAILABLE** | Excerpt does not name `docuflow-cleanup` |
| Render run id | **NOT AVAILABLE** | |
| Trigger (Scheduled / Manual) | **NOT AVAILABLE** | A11 §3 item 3 |
| Timestamp provenance | **OWNER-ASSERTED** | Owner confirmed UTC |
| Dashboard crop / Logs export | **NOT AVAILABLE** | |

Do not infer service identity from the earlier “cron job
production” fail-fast line. That was a different event.

## 5. Deployment-window correlation

Production OA-3 window start (A11 §3): **not before ~15:27**
13 Nov 2026 Asia/Jakarta, OWNER-PROVIDED Resume of `381b201`.

| Clock | Value |
| --- | --- |
| Owner UTC | `2026-11-13 14:02:46.536 UTC` |
| If UTC is correct | **13 Nov 2026, 21:02:46 Asia/Jakarta** |
| After ~15:27 Asia/Jakarta? | **Yes** (arithmetic) |
| Window end | **NOT PROVIDED** in A11; no expiry on this excerpt |

Timestamp-in-window (arithmetic): **VERIFIED** only **if** the
OWNER-ASSERTED UTC clock is accepted. Provenance remains
**OWNER-ASSERTED**.

| SHA item | Classification |
| --- | --- |
| `381b201` exists on git and is an ancestor of `origin/main` | **VERIFIED** (repository) |
| `381b201` includes `e9453bc` / #98 | Historical OWNER-PROVIDED + git ancestry **VERIFIED** |
| This Run’s deploy SHA is `381b201` | **OWNER-ASSERTED** (“deployment reference”) |
| Live cron still on `381b201` after #102/#103 | A11 gap: **NOT VERIFIED** |

A11 §3 item 2 requires the SHA **on that service for that Run**
from Deploys/header, not inferred from GitHub or from a prior
OWNER-PROVIDED capture.

## 6. Execution attribution

`cleanup_cli_ok` plus `cleanup_finished` `aborted=False` means:
the cleanup CLI body completed and was not skipped or aborted —
**if** the excerpt is authentic and from the named OA-3 cron.

It does **not** independently establish:

1. Service = `docuflow-cleanup`
2. Trigger = Scheduled
3. Deploy SHA on that Run = `381b201` or a descendant containing
   `e9453bc`
4. That this is OA-3 post-change execution rather than a later
   cleanup event on some other SHA

A11 §8 candidate **EXECUTION VERIFIED** requires the success
tokens **in window** **and** items 1–4. Missing metadata blocks
that upgrade.

OA-3 execution: **NOT VERIFIED**.

CONTROL-XWS / runtime isolation: unchanged **NOT VERIFIED**.
Success cleanup of zero objects is not isolation proof.

## 7. OA-A11-LOGS closure

**Not closed as VERIFIED.**

| A11 §3 item | Result |
| --- | --- |
| 1 Service identity | **NOT AVAILABLE** in this excerpt |
| 2 SHA on the Run | **OWNER-ASSERTED** only |
| 3 Scheduled trigger | **NOT AVAILABLE** |
| 4 Start inside window | Arithmetic **VERIFIED** if UTC accepted; provenance **OWNER-ASSERTED** |
| 5 Success tokens | **SOURCE-CONSISTENT** / **OWNER-ASSERTED** capture |
| 6 Not migrate-only | Tokens are cleanup body, not `alembic_upgrade_*` — **SOURCE-CONSISTENT** if authentic |

OA-A11-LOGS: **PARTIALLY VERIFIED** (success tokens
OWNER-ASSERTED + SOURCE-CONSISTENT). Fail-fast line from PR #109
remains on the ledger. Success artifacts are **not** independently
bound to the named cron Run.

Do not request a new cron execution solely to recreate these
tokens. Minimum **additional owner-supplied artifact** for the
**same** 14:02 UTC Run:

1. Service name `docuflow-cleanup` (or an explicit statement that
   this excerpt is from that cron).
2. Trigger label **Scheduled** (cropped Runs row).
3. Deploy SHA shown on that service for that Run (`381b201` or
   descendant containing `e9453bc`).
4. Optional: one raw JSON log object with `asctime`, `levelname`,
   `name`, `message`.

Do not paste secrets. Do not Trigger Run. Do not open Environment.

## 8. Status after this assessment

| Item | Status |
| --- | --- |
| Category A | **APPROVED** (read-only cron logs) |
| OA-A11-LOGS | **PARTIALLY VERIFIED** / **NOT VERIFIED** as closed |
| OA-3 execution | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| Runtime isolation | **NOT VERIFIED** |
| OA-5 | **IN FORCE** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Phase 10.4C | **NOT COMPLETE** |

## 9. Safety declaration

- No Production HTTP probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- Render Environment / Logs / Runs were not opened by this agent.
- No live database connections were made.
- No cleanup operation was executed (including `--dry-run`).
- Cron was not triggered or rescheduled.
- No storage objects were read, written, or deleted.
- No migrations, restore, or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment, Resume, or Suspend was performed.
- OA-3 was **not** executed by this agent.
- CONTROL-XWS was **not** executed.
- Phase 10.4C-B was not authorized or executed.
- OA-5 was **not** weakened.
- No success log was manufactured. Owner text was recorded as
  received.
