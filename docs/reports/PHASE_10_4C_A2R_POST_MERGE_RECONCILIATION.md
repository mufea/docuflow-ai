# Phase 10.4C-A2R — Post-merge documentation reconciliation

Documentation-only. Time: **13 Nov 2026, 09:22 Asia/Jakarta (WIB)**.
No application-code change. No Blueprint, env, deploy, migrate,
cleanup, object write, Production probe, or Stage B.

This report does **not** claim RUNTIME ISOLATION VERIFIED.

## A. Executive summary

Reconcile repository documentation after Phase 10.4C-A2 merged.

| Field | Result |
| --- | --- |
| Objective | Correct stale **COMPLETE – UNMERGED** after PR #89; record Gap 4 topology vs isolation limits |
| Baseline `origin/main` at start | `3e807db52939a21a02ca4c2cd09c99bf295b44ea` |
| PR #89 | **MERGED** into `main` |
| Reconciliation | 10.4C-A2 documentation is **MERGED**. Gap 1–3 preserved. Gap 4 workspace exclusivity remains **PASS** (OWNER-PROVIDED). Project membership and cross-workspace access remain **NOT VERIFIED**. Overall isolation **NOT VERIFIED**. Stage B **NOT AUTHORIZED** |

## B. GitHub verification

| Field | Verified value |
| --- | --- |
| PR | [#89](https://github.com/mufea/docuflow-ai/pull/89) |
| Title | docs: record 10.4C-A2 token scope and separate Render workspaces |
| State | **MERGED** |
| Base | `main` |
| Head | `cursor/phase-10-4c-a2-topology-evidence-8f43` |
| Merge commit | `3e807db52939a21a02ca4c2cd09c99bf295b44ea` |
| Merged at | `2026-11-13T02:15:24Z` / **13 Nov 2026, 09:15 Asia/Jakarta** |
| Files | `docs/IMPLEMENTATION_STATUS.md`, `docs/reports/PHASE_10_4C_A_RUNTIME_ISOLATION_ASSURANCE.md` |
| Last PR-head SHA | `8f75e95bc358e3b23848ec32f74b75b6807dddda` |
| PR-head CI | [43350648569](https://github.com/mufea/docuflow-ai/actions/runs/43350648569) **SUCCESS** (Python `131640613986`, Web `131640614262`) |
| `main` after merge | `3e807db52939a21a02ca4c2cd09c99bf295b44ea` |
| `main` push CI | [43350850093](https://github.com/mufea/docuflow-ai/actions/runs/43350850093) **SUCCESS** (Python `131641266729`, Web `131641267229`; completed `2026-11-13T02:17:04Z` / **13 Nov 2026, 09:17 Asia/Jakarta**) |

Repository CI is **not** runtime isolation. MERGED is **not** DEPLOYED.

On `origin/main` at this SHA, `docs/IMPLEMENTATION_STATUS.md` still
showed `PHASE 10.4C-A2 DOCUMENTATION: **COMPLETE – UNMERGED**`. That
current-status label is stale and is corrected by this phase.

## C. Render evidence

Evidence class: **OWNER-PROVIDED** screenshots already recorded in
`docs/reports/PHASE_10_4C_A_RUNTIME_ISOLATION_ASSURANCE.md` §14.
This recon did **not** open Render and did **not** re-interpret
pixels as independent verification.

### C.1 Workspaces (13 Nov 2026, 08:53–08:54 Asia/Jakarta)

| Workspace chrome | Observed |
| --- | --- |
| `docuflowai` | Project `Docuflow AI`, environment Production, All 6 Production-named services |
| `docuflowai staging` | Staging-named services as ungrouped inventory |

Separate **workspaces** are CONFIRMED as OWNER-PROVIDED dashboard
chrome. This recon does not independently verify Render workspace
ids.

Prompt transcription “docuflow staging” is not used. The recorded
chrome is `docuflowai staging`.

### C.2 Staging inventory (13 Nov 2026, 09:10 Asia/Jakarta)

Phone clock **9:10 AM**. Workspace chrome `docuflowai staging`.
Region oregon. Ungrouped Services Active 4 / Suspended 0 / **All 4**.

| Service | Observed status | Runtime |
| --- | --- | --- |
| `docuflow-staging-api` | Deployed | Python 3 |
| `docuflow-staging-cleanup` | Successful build | Python 3 |
| `docuflow-staging-db` | Available | PostgreSQL 16 |
| `docuflow-staging-web` | Deployed | Node |

Project named `staging`: **No active services**. Live services are
listed under **Ungrouped Services**, not under that project.

Limitations of this screenshot:

- It shows four staging-named services in the staging workspace
  inventory.
- It does **not** show those services as members of project
  `staging`.
- `Successful build` is not a cleanup job run and not a new identity
  SQL.
- `Available` on Postgres is not database isolation.
- `Deployed` is not functional verification.
- No Production-named services appear in All 4. That is an inventory
  observation, not a permission proof.

## D. Gap assessment

| Gap | Evidence | Classification | Outstanding limitation |
| --- | --- | --- | --- |
| 1 Cleanup DB identity | A1 labeled `docuflow-staging-cleanup` Shell (`docuflow_staging_db_ikpz` / `docuflow_staging_db_ikpz_user` / `10.26.149.13:5432`) | **PASS** OWNER-PROVIDED (unchanged) | Identity SQL not repeated after 09:10 rebuild. Cleanup R2 live env later **PASS** in isolation report §17. Cleanup not executed |
| 2 API R2 endpoint + masked key | A1 `docuflow-staging-api` Shell: `S3_BUCKET=docuflowai-staging`, host `26d06bf0ca16ba951f1d19d5989e6663.r2.cloudflarestorage.com`, key masked `6c01…2307` | **PASS** OWNER-PROVIDED (unchanged) | Cleanup env unread. Production negative access not tested |
| 3 Cloudflare token scope | A2 Cloudflare screenshot: token `docuflowai-staging`; read/write/list; bucket `docuflowai-staging` only | **PASS** OWNER-PROVIDED (unchanged) | Dashboard intent, not a Production-bucket negative probe |
| 4 Workspace exclusivity | 08:53–08:54 two workspace names; 09:10 Staging All 4 has no Production names | **PASS** OWNER-PROVIDED (unchanged) | Chrome names, not independently verified workspace ids |
| 4 Project membership | 09:10 ungrouped / empty project `staging` was **NOT VERIFIED**. 09:29 screenshot shows all four services in project `DocuflowAI`, environment Staging | **PASS** OWNER-PROVIDED (09:29). 09:10 remains historical | Not a cross-workspace permission proof. Empty project `staging` vs `DocuflowAI` is not independently explained |
| 4 Cross-workspace access | No permission, network, or negative-access evidence | **NOT VERIFIED** | Separate workspaces are not proof that Staging cannot reach Production resources |
| 4 as a complete isolation control | Topology plus inventory only | **PARTIALLY VERIFIED** | Workspace exclusivity PASS does not equal runtime isolation PASS |

A1/A2 historical timestamps are preserved. 08:46 same-workspace
**NOT MET** remains historical. 08:54 All 3 (cleanup missing) remains
historical.

## E. Remaining risks

1. Cross-workspace access isolation is **NOT VERIFIED**.
2. Project membership of the four staging services is **PASS** as of
   09:29 (OWNER-PROVIDED project `DocuflowAI`, environment Staging).
   The 09:10 ungrouped / empty `staging` project record is historical.
3. Overall runtime isolation is **NOT VERIFIED**.
4. Functional Staging verification is **NOT VERIFIED**. Stage B is
   **NOT AUTHORIZED**.
5. Production verification is **NOT VERIFIED**.
6. Cleanup live R2 env / HeadBucket unread.
7. Render resource id for observed Postgres IP unread.
8. Next phase requires a **separate** owner authorization. This recon
   does not authorize Phase 10.4C-B.

## F. Safety declaration

This phase:

- Did not access Production or Staging shells.
- Did not connect to any database.
- Did not access R2.
- Did not run cleanup, migrate, deploy, restore, or export.
- Did not change Render, Cloudflare, DNS, or credentials.
- Did not modify `src/`, `apps/`, `packages/`, or `infra/`.
- Did not print DSNs, tokens, or secret keys.

## G. Final decision

| Label | Result |
| --- | --- |
| PHASE 10.4C-A2 DOCUMENTATION | **MERGED** (PR #89, `3e807db`) |
| PHASE 10.4C-A2R DOCUMENTATION | **MERGED** (PR #90, `eda7c6c`) |
| RUNTIME ISOLATION VERIFIED | **NO** |
| FUNCTIONAL STAGING VERIFIED | **NO** |
| PRODUCTION VERIFIED | **NO** |
| Phase 10.4C-B | **NOT AUTHORIZED** |

Phase 10.4C-A2R is complete as documentation reconciliation ready for
owner review. The next phase is **not** authorized.
