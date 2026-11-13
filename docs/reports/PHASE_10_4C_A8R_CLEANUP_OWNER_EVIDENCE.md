# Phase 10.4C-A8R — Cleanup owner evidence (Runs and Deploys)

Documentation-only. First capture **13 Nov 2026, 15:19–15:27
Asia/Jakarta (WIB)** (Runs). Second capture **15:32 Asia/Jakarta**
(Deploys). Owner / Approver: EDY ALAMSAH. No application-code
change. No Render Shell, logs, Trigger Run, cleanup (including
`--dry-run`), database, storage, deploy, or Stage B.

OA-5 remains **IN FORCE**. This pass records owner-supplied
screenshots only. The agent did **not** open Render.

## 1. Executive summary

A8 asked for cropped cleanup SHA evidence. The owner sent **Runs**
then **Deploys** tabs. Both services currently show git
**`381b201` Latest** on `main`. That commit is current
`origin/main` and **includes** PR #97 and PR #98.

Staging Auto-Deployed `#97`, `#98`, and `#101`. Production jumped
from PR `#44` to `#101` with trigger **Resumed**; `#97`/`#98` are
included only as ancestors of `381b201`.

Last **successful** cron runs still predate a verified OA-3
execution. Failure cause is **NOT VERIFIED** (no logs).

| Field | Result |
| --- | --- |
| `origin/main` | `381b20191c0fbab78b39eb309f3e8c37d2ebecf8` |
| Staging cleanup current deploy | `381b201` Auto-Deploy ~**15:17** (15m before 15:32) |
| Production cleanup current deploy | `381b201` **Resumed** ~**15:27** (5m before 15:32) |
| Includes PR #97 / #98? | **yes** (ancestry of `381b201`) |
| Staging last successful run | **13 Nov 2026, 14:00 Asia/Jakarta** |
| Production last successful run | **10 Nov 2026, 16:30 Asia/Jakarta** |
| Successful run of OA-3 code | **NOT VERIFIED** |
| Phase 10.4C-B | **NOT AUTHORIZED** |

## 2. Verified repository baseline

`git fetch origin main`. Working tree clean before branch create.

| Field | Value |
| --- | --- |
| `origin/main` HEAD | `381b20191c0fbab78b39eb309f3e8c37d2ebecf8` |
| Subject | Merge pull request #101 |
| Commit date | `2026-11-13T15:16:19+07:00` / **13 Nov 2026, 15:16 Asia/Jakarta** |
| Ancestor of #97 `cf0d615` | **yes** |
| Ancestor of #98 `e9453bc` | **yes** |
| Live resources contacted | **none** |
| Render dashboard opened by agent | **no** |

A8 (`docs/reports/PHASE_10_4C_A8_DEPLOYMENT_EVIDENCE_ASSESSMENT.md`)
classified cleanup SHAs as **NOT VERIFIED** because GitHub
Deployments has **no** cleanup records. That GitHub gap remains.
This pass adds **OWNER-PROVIDED** header SHAs only.

PR [#102](https://github.com/mufea/docuflow-ai/pull/102) repository
CI: **SUCCESS**
[43393620601](https://github.com/mufea/docuflow-ai/actions/runs/43393620601)
(Python `131779188696`, Web `131779188984`; **13 Nov 2026, 15:31
Asia/Jakarta**). Repository CI is not isolation and is not a deploy.

## 3. Evidence class

| Item | Class |
| --- | --- |
| Screenshots | **OWNER-PROVIDED** (phone; Runs **15:19/15:27**, Deploys **15:32 Asia/Jakarta**) |
| Tabs captured | **Runs** (15:19 / 15:27) then **Deploys** (15:32) |
| Git SHA in header | Render service pin `381b201` **Latest** |
| Cron success/fail dots | Visible on Runs list; **not** log content |
| GitHub Deployments for cleanup | still **none** |

The header SHA plus Deploys rows are the A8-requested commit
identifier and deploy event. They are **not** proof that a cron
run of that SHA succeeded.

## 4. Staging — `docuflow-staging-cleanup`

Workspace shown: **docuflowai staging**. Cron job. Blueprint
managed. Command: `python -m docuflow.migrate && python -m
docuflow.cleanup` every 15 minutes.

| Field | Owner-visible value |
| --- | --- |
| Service | `docuflow-staging-cleanup` |
| Git | `mufea/docuflow-ai` `main` **`381b201` Latest** |
| Last successful run | November 13, 2026 at 2:00 PM GMT+7 / **13 Nov 2026, 14:00 Asia/Jakarta** |
| Deploy timestamp (Runs tab) | **not on Runs screenshot**; see §6 |
| Recent Runs | red (failed) at ~4m, 19m, 34m, 49m, 1h; older green (success) ~1h–2h |

| Question | Result |
| --- | --- |
| Header SHA includes #97? | **yes** |
| Header SHA includes #98? | **yes** |
| Last success vs OA-2 merge `cf0d615` (13:56) | last success **14:00** is **after** OA-2 |
| Last success vs OA-3 merge `e9453bc` (14:08) | last success **14:00** is **before** OA-3 |
| Successful OA-3 cron run | **NOT VERIFIED** |
| Failure cause | **NOT VERIFIED** (logs not opened) |
| Classification (header SHA) | **VERIFIED** (OWNER-PROVIDED `381b201`) |
| Classification (deploy event) | **VERIFIED** (Deploys tab; see §6) |
| Classification (healthy run of current SHA) | **NOT VERIFIED** |

Do **not** treat red Runs as a diagnosed OA-3 fail-fast. That
would require logs, which OA-5 forbids unless separately approved.

## 5. Production — `docuflow-cleanup`

Workspace shown: **docuflowai**. Cron job. Blueprint managed. Same
start command every 15 minutes.

| Field | Owner-visible value |
| --- | --- |
| Service | `docuflow-cleanup` |
| Git | `mufea/docuflow-ai` `main` **`381b201` Latest** |
| Last successful run | November 10, 2026 at 4:30 PM GMT+7 / **10 Nov 2026, 16:30 Asia/Jakarta** |
| Deploy timestamp (Runs tab) | **not on Runs screenshot**; see §6 |
| Recent Runs | red Manual **~1m ago** “by you”; older green Scheduled ~2d–4d |

A3 recorded Production cleanup as **Suspended**. The later Deploys
tab shows trigger **Resumed** for `381b201` (~15:27). That is
OWNER-PROVIDED deploy-event evidence, not an owner-authorized live
cleanup and not a successful OA-3 run.

| Question | Result |
| --- | --- |
| Header SHA includes #97 / #98? | **yes** |
| Last success vs OA-2 / OA-3 | **10 Nov 2026** — **before** both merges |
| Successful run of `381b201` | **NOT VERIFIED** |
| Manual run ~15:26 | failed; cause **NOT VERIFIED** |
| Classification (header SHA) | **VERIFIED** (OWNER-PROVIDED `381b201`) |
| Classification (deploy event) | **VERIFIED** (Deploys tab; see §6) |
| Classification (healthy run of current SHA) | **NOT VERIFIED** |

The agent did **not** press Trigger Run. The Manual row is
owner-visible on the screenshot.

## 6. Deploys tabs (second owner capture)

Phone clock **15:32 Asia/Jakarta**. **Deploys** selected. Relative
“Deployed Xm ago” times are converted from that clock.

### Staging `docuflow-staging-cleanup`

| Deploy row | SHA | Trigger | Relative | Approx. time (Asia/Jakarta) |
| --- | --- | --- | --- | --- |
| PR #101 (current) | `381b201` | Auto-Deploy | 15m ago | **~15:17** |
| PR #100 | `ec3d079` | Auto-Deploy | 33m ago | **~14:59** |
| PR #99 | `06ba141` | Auto-Deploy | 1h ago | **~14:32** |
| PR #98 (OA-3) | `e9453bc` | Auto-Deploy | 1h ago | **~14:32** |
| PR #97 (OA-2) | `cf0d615` | Auto-Deploy | 1h ago | **~14:32** |

All visible rows are green. Staging Auto-Deployed OA-2 and OA-3
as separate events, then later `#101`.

### Production `docuflow-cleanup`

| Deploy row | SHA | Trigger | Relative | Approx. time (Asia/Jakarta) |
| --- | --- | --- | --- | --- |
| PR #101 (current) | `381b201` | **Resumed** | 5m ago | **~15:27** |
| PR #44 | `bed6140` | Auto-Deploy | 2d ago | **~11 Nov 2026** |

No Deploys row for `#97` or `#98`. Those commits are on
`381b201` by git ancestry only. **Resumed** matches A3
**Suspended** topology: Production cleanup was not taking the
OA-2/OA-3 Auto-Deploys while skipped.

| Service | Current SHA | Trigger | Deploy time | #97/#98 |
| --- | --- | --- | --- | --- |
| Staging cleanup | `381b201` | Auto-Deploy | **~15:17** | **yes** (also separate `#97`/`#98` rows) |
| Production cleanup | `381b201` | Resumed | **~15:27** | **yes** (ancestry only) |

Classification: cleanup **deploy SHA + timestamp** **VERIFIED**
(OWNER-PROVIDED Deploys). Successful OA-3 **run** remains
**NOT VERIFIED**.

## 7. OA-2 / OA-3 inclusion after this evidence

| Surface | #97 OA-2 | #98 OA-3 | Notes |
| --- | --- | --- | --- |
| Staging API (A8 GitHub) | included (`ec3d079`) | included | GitHub Render App **success** |
| Production API (A8 GitHub) | included (`ec3d079`) | included | GitHub Render App **success** |
| Staging cleanup deploy | included (`381b201`; also `cf0d615` / `e9453bc` rows) | included | OWNER-PROVIDED Deploys; Auto-Deploy |
| Production cleanup deploy | included (`381b201` ancestry) | included | OWNER-PROVIDED Deploys; **Resumed**; no `#97`/`#98` rows |
| Staging cleanup last **success** | possibly (14:00 after OA-2) | **no** (14:00 before OA-3) | later Runs failed |
| Production cleanup last **success** | **no** (10 Nov) | **no** (10 Nov) | later Manual failed |

API inclusion remains GitHub-VERIFIED from A8. Cleanup **deploy
SHA** is OWNER-PROVIDED **VERIFIED**. Cleanup **successful
execution** of OA-3 is **NOT VERIFIED**.

## 8. Remaining gaps

1. GitHub Deployments still has **no** cleanup environments
   (cron Auto-Deploy / Resume does not appear there).
2. Cron failure logs: **not** collected (OA-5).
3. CONTROL-XWS: **NOT VERIFIED**.
4. Phase 10.4C-B: **NOT AUTHORIZED**.

Do **not** approve log inspection or live `--dry-run` in this
report.

## 9. Owner action register

| ID | Status |
| --- | --- |
| OA-5 | **IN FORCE** |
| OA-A8-S-CLEAN (Runs + header SHA) | **PROVIDED** |
| OA-A8-P-CLEAN (Runs + header SHA) | **PROVIDED** |
| OA-A8-S-DEPLOY (Deploys tab) | **PROVIDED** (15:32) |
| OA-A8-P-DEPLOY (Deploys tab) | **PROVIDED** (15:32) |
| OA-6 Phase 10.4C-B | **NOT APPROVED** |
| Live cleanup / log read | **NOT AUTHORIZED** |

## 10. Recommendation

| Question | Recommendation |
| --- | --- |
| Does cleanup **deploy** include #97/#98? | **YES** — current SHA `381b201` |
| Did a **successful** Staging OA-3 run occur? | **NO-GO** — last success **before** OA-3; later red |
| Did a **successful** Production OA-3 run occur? | **NO-GO** — last success **10 Nov 2026** |
| Open logs / Shell to explain red Runs? | **NO-GO** — OA-5 |
| Phase 10.4C-B? | **NO-GO** |
| Overall runtime isolation | **NOT VERIFIED** |

## 11. Classifications

| Label | Result |
| --- | --- |
| OVERALL RUNTIME ISOLATION | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| PHASE 10.4C | **NOT COMPLETE** |
| PHASE 10.4C-B | **NOT AUTHORIZED** |
| OA-5 | **IN FORCE** |
| Staging API deploy SHA | **VERIFIED** (A8 GitHub; unchanged) |
| Production API deploy SHA | **VERIFIED** (A8 GitHub; unchanged) |
| Staging cleanup deploy SHA | **VERIFIED** (OWNER-PROVIDED `381b201` Auto-Deploy ~15:17) |
| Production cleanup deploy SHA | **VERIFIED** (OWNER-PROVIDED `381b201` Resumed ~15:27) |
| Staging cleanup successful OA-3 run | **NOT VERIFIED** |
| Production cleanup successful OA-3 run | **NOT VERIFIED** |
| LIVE CLEANUP | **NOT AUTHORIZED** |

Safety declaration:

- No Production probes were performed by this agent.
- No Production or Staging Shell commands were executed.
- No live database connections were made.
- No cleanup operation was executed by this agent.
- No storage objects were read, written, or deleted.
- No migrations were executed.
- No restore or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment was performed.
- Render dashboards were not opened by this agent.
- Phase 10.4C-B was not authorized or executed.
