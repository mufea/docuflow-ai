# Phase 10.4C-A8 — Deployment evidence collection and readiness

Documentation-only. Time: **13 Nov 2026, 15:10 Asia/Jakarta (WIB)**.
Owner / Approver: EDY ALAMSAH. No application-code change. No
Blueprint, env, deploy, migrate, cleanup (including `--dry-run`),
object I/O, Render Shell, Production or Staging probe, or Stage B.

OA-5 remains **IN FORCE**. MERGED is **not** DEPLOYED by itself.
CI SUCCESS is **not** isolation. A GitHub-reported deploy SHA
establishes **commit inclusion** on that named service only. It
does **not** prove runtime behavior, isolation, or a cleanup run.

## 1. Executive summary

Assess whether PR #97 (OA-2 Production bucket helper) and PR #98
(OA-3 cleanup CLI safety) are demonstrably included in current
Staging and Production deployments.

| Field | Result |
| --- | --- |
| `origin/main` | `ec3d0795bf24d731559f5baebc97213a42415b88` |
| Previous milestone | PR #100 **MERGED** (exact match of expected SHA) |
| Staging API deploy SHA | `ec3d079` — GitHub Render App **success** |
| Production API deploy SHA | `ec3d079` — GitHub Render App **success** |
| Staging cleanup deploy SHA | **none** in GitHub Deployments |
| Production cleanup deploy SHA | **none** in GitHub Deployments |
| OA-2 / OA-3 on API | **included** (`ec3d079` ancestors #97 and #98) |
| OA-2 / OA-3 on cleanup | **NOT VERIFIED** |
| Runtime isolation | **NOT VERIFIED** |
| Phase 10.4C-B | **NOT AUTHORIZED** |

## 2. Verified repository baseline

`git fetch origin main`. Working tree clean before branch create.

| Field | Value |
| --- | --- |
| Expected previous merge | `ec3d0795bf24d731559f5baebc97213a42415b88` |
| `origin/main` HEAD | `ec3d0795bf24d731559f5baebc97213a42415b88` |
| Match | **exact** |
| Subject | Merge pull request #100 |
| Commit date | `2026-11-13T14:58:46+07:00` / **13 Nov 2026, 14:58 Asia/Jakarta** |
| Merged by | `mufea` |
| Inspector | Cursor Agent (this workspace) |
| Live resources contacted | **none** |
| Render dashboard opened | **no** |
| Render / Cloudflare APIs | **not** called |

Inspected (read-only):

- `docs/IMPLEMENTATION_STATUS.md` (A7 still **COMPLETE – UNMERGED**)
- `docs/reports/PHASE_10_4C_A7_POST_MERGE_LEDGER_AND_DEPLOYMENT_READINESS.md`
- `docs/DEPLOYMENT.md` (does not record a current live SHA)
- `infra/render.yaml`, `infra/render.staging.yaml`
- GitHub PRs #97, #98, #100
- GitHub Actions CI on `ec3d079`
- GitHub Deployments created by the Render GitHub App

A7 recorded Staging/Production SHAs as **UNAVAILABLE** and stated
that GitHub metadata had no Render deploy SHA. A7 did not query
the GitHub Deployments API. This pass does. A7 historical text is
preserved; current evidence is this report.

## 3. PR merge and source evidence

| PR | Role | Implementation | Merge SHA | Merged |
| --- | --- | --- | --- | --- |
| [#97](https://github.com/mufea/docuflow-ai/pull/97) | OA-2 helper | `ac36d9a` (`staging_checks.py`, tests, docs) | `cf0d615c476b43c1247876835d03482ecb7de2b9` | **13 Nov 2026, 13:56 Asia/Jakarta** |
| [#98](https://github.com/mufea/docuflow-ai/pull/98) | OA-3 CLI | `f82f76a` (`cleanup.py`, `scheduler.py`, tests, docs) | `e9453bc1436a66459d4ba6eab954ef5c70624392` | **13 Nov 2026, 14:08 Asia/Jakarta** |
| [#100](https://github.com/mufea/docuflow-ai/pull/100) | A7 docs | docs only | `ec3d0795bf24d731559f5baebc97213a42415b88` | **13 Nov 2026, 14:58 Asia/Jakarta** |

`cf0d615` and `e9453bc` **are** ancestors of `ec3d079`. Therefore
any service whose deployed commit is `ec3d079` (or a descendant)
**includes** both source changes.

Blueprints were **not** changed by #97 or #98. `previewsEnabled:
false`. No `autoDeploy` key in repo YAML. Blueprint files are
templates, not live SHA proof.

## 4. CI evidence

| Event | Run | Result | Time (Asia/Jakarta) |
| --- | --- | --- | --- |
| PR #97 head | [43381680153](https://github.com/mufea/docuflow-ai/actions/runs/43381680153) | **SUCCESS** | 13 Nov 2026, 13:54 |
| `main` after #97 | [43382133668](https://github.com/mufea/docuflow-ai/actions/runs/43382133668) | **SUCCESS** | 13 Nov 2026, 13:58 |
| PR #98 head | [43382801577](https://github.com/mufea/docuflow-ai/actions/runs/43382801577) | **SUCCESS** | 13 Nov 2026, 14:03 |
| `main` after #98 | [43383597847](https://github.com/mufea/docuflow-ai/actions/runs/43383597847) | **SUCCESS** | 13 Nov 2026, 14:10 |
| PR #100 head | [43388760245](https://github.com/mufea/docuflow-ai/actions/runs/43388760245) | **SUCCESS** | 13 Nov 2026, 14:53 |
| `main` after #100 | [43389637969](https://github.com/mufea/docuflow-ai/actions/runs/43389637969) | **SUCCESS** (Python `131766211213`, Web `131766210919`) | 13 Nov 2026, 15:00 |

Repository CI is **not** a Render deploy and is **not** isolation.

## 5. GitHub Deployments (Render GitHub App)

Queried `GET /repos/mufea/docuflow-ai/deployments` (GitHub
metadata only). Creator app: `render`. Dashboard URLs in status
payloads were **not** opened.

Environments that have **any** GitHub Deployment records:

- `main - docuflow-api`
- `main - docuflow-web`
- `main - docuflow-staging-api`
- `main - docuflow-staging-web`
- `main - docuflow-staging-db` (historical)
- `main - docuflow-db` (historical)
- `main - docuflow-worker` (last **31 Oct 2026**; not current SHA)

Environments with **zero** GitHub Deployment records:

- `docuflow-staging-cleanup`
- `docuflow-cleanup`

GitHub sets `production_environment: true` on Staging API/web
records as well. That flag is **not** used as Production proof.

Latest records for SHA `ec3d079` (after PR #100 merge):

| GitHub environment | Deployment id | Latest status | Status time (UTC) | Status time (Asia/Jakarta) |
| --- | --- | --- | --- | --- |
| `main - docuflow-staging-api` | `7760248453` | **success** | `2026-11-13T08:00:43Z` | **13 Nov 2026, 15:00** |
| `main - docuflow-api` | `7760248463` | **success** | `2026-11-13T08:00:43Z` | **13 Nov 2026, 15:00** |
| `main - docuflow-staging-web` | `7760248486` | **success** | `2026-11-13T08:00:02Z` | **13 Nov 2026, 15:00** |
| `main - docuflow-web` | `7760248505` | **success** | `2026-11-13T08:00:02Z` | **13 Nov 2026, 15:00** |

Each record went `in_progress` then `success` on that SHA.
Earlier **success** records exist on the same four services for
`cf0d615` (#97 merge) and `e9453bc` (#98 merge).

Limits of this evidence:

- It is GitHub-reported Render App metadata, not a live process
  inspection.
- One service’s success does **not** prove another service.
- Cron cleanup services are absent from this API.
- Historical 10.4B notes Staging auto-deploy **off**; this phase
  did **not** re-read that dashboard setting. The GitHub records
  exist regardless.

## 6. Staging deployment evidence matrix

| Service | Deploy SHA | Timestamp | Status | Evidence source | PR #97 | PR #98 | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `docuflow-staging-api` | `ec3d0795bf24d731559f5baebc97213a42415b88` | **13 Nov 2026, 15:00 Asia/Jakarta** | GitHub `success` | GitHub Deployment `7760248453` (Render App) | **yes** (ancestor) | **yes** (ancestor) | **VERIFIED** (commit inclusion) |
| `docuflow-staging-cleanup` | **none recorded** | **none** | **no GitHub record** | GitHub Deployments (empty for this name); A3 owner inventory said **Successful build** without a SHA | **NOT VERIFIED** | **NOT VERIFIED** | **NOT VERIFIED** |

Web (`docuflow-staging-web`) also has GitHub `success` on
`ec3d079`. It is **out of required scope** and is not used as
proof of API or cleanup.

A3 **Successful build** is not a cleanup run and is not a SHA.

## 7. Production deployment evidence matrix

| Service | Deploy SHA | Timestamp | Status | Evidence source | PR #97 | PR #98 | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `docuflow-api` | `ec3d0795bf24d731559f5baebc97213a42415b88` | **13 Nov 2026, 15:00 Asia/Jakarta** | GitHub `success` | GitHub Deployment `7760248463` (Render App) | **yes** (ancestor) | **yes** (ancestor) | **VERIFIED** (commit inclusion) |
| `docuflow-cleanup` | **none recorded** | **none** | **no GitHub record** | GitHub Deployments (empty for this name); A3 owner inventory said **Suspended** without a SHA | **NOT VERIFIED** | **NOT VERIFIED** | **NOT VERIFIED** |

Web (`docuflow-web`) also has GitHub `success` on `ec3d079`. Out
of required scope. Not proof of API or cleanup.

A3 Production cleanup **Suspended** is historical topology, not a
current SHA.

## 8. OA-2 and OA-3 deployment inclusion

| Surface | OA-2 (#97) | OA-3 (#98) |
| --- | --- | --- |
| Source on `main` | **PASS** | **PASS** |
| Staging API process (GitHub SHA) | **included** | **included** |
| Production API process (GitHub SHA) | **included** | **included** |
| Staging cleanup process | **NOT VERIFIED** | **NOT VERIFIED** |
| Production cleanup process | **NOT VERIFIED** | **NOT VERIFIED** |
| Live `--dry-run` / mutating cleanup | **NOT AUTHORIZED** | **NOT AUTHORIZED** |
| Runtime isolation | **NOT VERIFIED** | **NOT VERIFIED** |

OA-3 safeguards take effect on a **running cleanup CLI or
in-process scheduler**. API inclusion of `cleanup.py` does not
prove the cron service runs that SHA.

## 9. Missing evidence

1. GitHub Deployments SHA for `docuflow-staging-cleanup`.
2. GitHub Deployments SHA for `docuflow-cleanup`.
3. Owner dashboard corroboration of those cleanup SHAs (service
   name, status, commit SHA, timestamp only).
4. Current auto-deploy setting (historical 10.4B: off; not
   re-checked).
5. Live runtime behavior of OA-2 / OA-3 (not in scope; OA-5).
6. CONTROL-XWS remains **NOT VERIFIED** (OA-1 Option A).

## 10. Minimal owner action register

Do **not** send Environment Variables, secrets, DSNs, tokens, or
Shell output.

| ID | Action | Status |
| --- | --- | --- |
| OA-5 | Standing prohibition | **IN FORCE** |
| OA-A8-S-CLEAN | Cropped Staging screenshot: service `docuflow-staging-cleanup`; deploy status; commit SHA; timestamp | **NOT PROVIDED** |
| OA-A8-P-CLEAN | Cropped Production screenshot: service `docuflow-cleanup`; deploy status; commit SHA; timestamp | **NOT PROVIDED** |
| OA-6 | “APPROVE Phase 10.4C-B” naming allowed Staging tests | **NOT APPROVED** |
| Live cleanup | Separate APPROVE naming Staging-only dry-run or run | **NOT AUTHORIZED** |

Optional (not required for API commit-inclusion already recorded
from GitHub): cropped Staging/Production API commit rows. Do not
treat this report as having received those screenshots.

The owner capturing dashboard rows is an **owner** action. This
phase does **not** authorize the agent to open Render.

## 11. Final deployment readiness recommendation

| Question | Recommendation |
| --- | --- |
| Are #97 and #98 on Staging API? | **YES** — GitHub Render App SHA `ec3d079` |
| Are #97 and #98 on Production API? | **YES** — GitHub Render App SHA `ec3d079` |
| Are they on Staging cleanup? | **NO-GO** — SHA **NOT VERIFIED** |
| Are they on Production cleanup? | **NO-GO** — SHA **NOT VERIFIED** |
| Treat environments as fully updated? | **NO-GO** — cleanup in required scope is missing |
| Deploy / restart now? | **NO-GO** — OA-5; not requested |
| Live cleanup now? | **NO-GO** |
| Phase 10.4C-B now? | **NO-GO** |
| Overall runtime isolation | **NOT VERIFIED** |

## 12. Classifications

| Label | Result |
| --- | --- |
| OVERALL RUNTIME ISOLATION | **NOT VERIFIED** |
| CONTROL-XWS | **NOT VERIFIED** |
| PHASE 10.4C | **NOT COMPLETE** |
| PHASE 10.4C-B | **NOT AUTHORIZED** |
| OA-5 | **IN FORCE** |
| Staging API deploy SHA | **VERIFIED** (`ec3d079`; includes #97/#98) |
| Production API deploy SHA | **VERIFIED** (`ec3d079`; includes #97/#98) |
| Staging cleanup deploy SHA | **NOT VERIFIED** |
| Production cleanup deploy SHA | **NOT VERIFIED** |
| LIVE CLEANUP | **NOT AUTHORIZED** |
| DEPLOY (new / restart) | **NOT AUTHORIZED** |

Safety declaration:

- No Production probes were performed.
- No Production or Staging Shell commands were executed.
- No live database connections were made.
- No cleanup operation was executed.
- No storage objects were read, written, or deleted.
- No migrations were executed.
- No restore or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment was performed.
- Render dashboards were not opened.
- Phase 10.4C-B was not authorized or executed.
