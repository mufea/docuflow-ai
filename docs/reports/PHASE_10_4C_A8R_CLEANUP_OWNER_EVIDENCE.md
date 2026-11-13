# Phase 10.4C-A8R — Cleanup owner evidence (Runs screenshots)

Documentation-only. Time: **13 Nov 2026, 15:27 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. No application-code change. No
Render Shell, logs, Trigger Run, cleanup (including `--dry-run`),
database, storage, deploy, or Stage B.

OA-5 remains **IN FORCE**. This pass records owner-supplied
screenshots only. The agent did **not** open Render.

## 1. Executive summary

A8 asked for cropped cleanup SHA evidence. The owner sent **Runs**
tabs (not Deploys) for both cron services. Both headers show git
**`381b201` Latest** on `main`. That commit is current
`origin/main` and **includes** PR #97 and PR #98.

Last **successful** cron runs predate a verified OA-3 execution.
Recent visible runs failed. Failure cause is **NOT VERIFIED** (no
logs).

| Field | Result |
| --- | --- |
| `origin/main` | `381b20191c0fbab78b39eb309f3e8c37d2ebecf8` |
| Staging cleanup header SHA | `381b201` **Latest** (OWNER-PROVIDED) |
| Production cleanup header SHA | `381b201` **Latest** (OWNER-PROVIDED) |
| Includes PR #97 / #98? | **yes** (git ancestry of `381b201`) |
| Deploys tab / deploy timestamp | **not shown** |
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
| Screenshots | **OWNER-PROVIDED** (phone; **13 Nov 2026, 15:19** and **15:27 Asia/Jakarta**) |
| Tab captured | **Runs**, not **Deploys** |
| Git SHA in header | Render service pin `381b201` **Latest** |
| Cron success/fail dots | Visible on Runs list; **not** log content |
| GitHub Deployments for cleanup | still **none** |

The header SHA is the A8-requested commit identifier. It is **not**
a Deploys-row timestamp. It is **not** proof that a cron run of
that SHA succeeded.

## 4. Staging — `docuflow-staging-cleanup`

Workspace shown: **docuflowai staging**. Cron job. Blueprint
managed. Command: `python -m docuflow.migrate && python -m
docuflow.cleanup` every 15 minutes.

| Field | Owner-visible value |
| --- | --- |
| Service | `docuflow-staging-cleanup` |
| Git | `mufea/docuflow-ai` `main` **`381b201` Latest** |
| Last successful run | November 13, 2026 at 2:00 PM GMT+7 / **13 Nov 2026, 14:00 Asia/Jakarta** |
| Deploy timestamp | **not on this screenshot** |
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
| Classification (deploy event) | **NOT VERIFIED** (Deploys tab absent) |
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
| Deploy timestamp | **not on this screenshot** |
| Recent Runs | red Manual **~1m ago** “by you”; older green Scheduled ~2d–4d |

A3 recorded Production cleanup as **Suspended**. This screenshot
shows a live Runs list (scheduled history and a manual trigger).
Suspend/resume **setting** was not captured. Do not infer the
toggle from Runs alone beyond: runs exist in this UI.

| Question | Result |
| --- | --- |
| Header SHA includes #97 / #98? | **yes** |
| Last success vs OA-2 / OA-3 | **10 Nov 2026** — **before** both merges |
| Successful run of `381b201` | **NOT VERIFIED** |
| Manual run ~15:26 | failed; cause **NOT VERIFIED** |
| Classification (header SHA) | **VERIFIED** (OWNER-PROVIDED `381b201`) |
| Classification (deploy event) | **NOT VERIFIED** |
| Classification (healthy run of current SHA) | **NOT VERIFIED** |

The agent did **not** press Trigger Run. The Manual row is
owner-visible on the screenshot.

## 6. OA-2 / OA-3 inclusion after this evidence

| Surface | #97 OA-2 | #98 OA-3 | Notes |
| --- | --- | --- | --- |
| Staging API (A8 GitHub) | included (`ec3d079`) | included | GitHub Render App **success** |
| Production API (A8 GitHub) | included (`ec3d079`) | included | GitHub Render App **success** |
| Staging cleanup header | included (`381b201`) | included | OWNER-PROVIDED; Deploys tab absent |
| Production cleanup header | included (`381b201`) | included | OWNER-PROVIDED; Deploys tab absent |
| Staging cleanup last **success** | possibly (14:00 after OA-2) | **no** (14:00 before OA-3) | later Runs failed |
| Production cleanup last **success** | **no** (10 Nov) | **no** (10 Nov) | later Manual failed |

API inclusion remains GitHub-VERIFIED from A8. Cleanup **source
pin** is now OWNER-PROVIDED. Cleanup **successful execution** of
OA-3 is **NOT VERIFIED**.

## 7. Remaining gaps

1. Deploys tab (deploy status + timestamp) still missing for both
   cleanup services.
2. GitHub Deployments still has **no** cleanup environments.
3. Cron failure logs: **not** collected (OA-5).
4. CONTROL-XWS: **NOT VERIFIED**.
5. Phase 10.4C-B: **NOT AUTHORIZED**.

Optional later owner capture (no secrets, no Shell, no env
values): Deploys tab showing commit SHA, deploy status, and
timestamp only.

Do **not** approve log inspection or live `--dry-run` in this
report.

## 8. Owner action register

| ID | Status |
| --- | --- |
| OA-5 | **IN FORCE** |
| OA-A8-S-CLEAN (Runs + header SHA) | **PROVIDED** (this pass) |
| OA-A8-P-CLEAN (Runs + header SHA) | **PROVIDED** (this pass) |
| OA-A8-S-DEPLOY (Deploys tab) | **NOT PROVIDED** |
| OA-A8-P-DEPLOY (Deploys tab) | **NOT PROVIDED** |
| OA-6 Phase 10.4C-B | **NOT APPROVED** |
| Live cleanup / log read | **NOT AUTHORIZED** |

## 9. Recommendation

| Question | Recommendation |
| --- | --- |
| Does cleanup **header** include #97/#98? | **YES** — `381b201` |
| Did a **successful** Staging OA-3 run occur? | **NO-GO** — last success **before** OA-3; later red |
| Did a **successful** Production OA-3 run occur? | **NO-GO** — last success **10 Nov 2026** |
| Open logs / Shell to explain red Runs? | **NO-GO** — OA-5 |
| Phase 10.4C-B? | **NO-GO** |
| Overall runtime isolation | **NOT VERIFIED** |

## 10. Classifications

| Label | Result |
| --- | --- |
| OVERALL RUNTIME ISOLATION | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| PHASE 10.4C | **NOT COMPLETE** |
| PHASE 10.4C-B | **NOT AUTHORIZED** |
| OA-5 | **IN FORCE** |
| Staging API deploy SHA | **VERIFIED** (A8 GitHub; unchanged) |
| Production API deploy SHA | **VERIFIED** (A8 GitHub; unchanged) |
| Staging cleanup header SHA | **VERIFIED** (OWNER-PROVIDED `381b201`) |
| Production cleanup header SHA | **VERIFIED** (OWNER-PROVIDED `381b201`) |
| Staging cleanup deploy timestamp | **NOT VERIFIED** |
| Production cleanup deploy timestamp | **NOT VERIFIED** |
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
