# Phase 10.4C-A4 — Owner-gated isolation verification plan

Documentation-only planning phase. Time: **13 Nov 2026, 11:14
Asia/Jakarta (WIB)**. No application-code change. No Blueprint, env,
deploy, migrate, cleanup execution, object I/O, Production probe,
Staging functional smoke, cross-workspace access attempt, or Stage B.

This report is a **plan**, not runtime verification.
A proposed test is **not** evidence that the test passed.
A merged report is **not** isolation.

Authoritative classifications (unchanged from Phase 10.4C-A3):

- Overall runtime isolation: **NOT VERIFIED**
- Phase 10.4C: **NOT COMPLETE**
- Phase 10.4C-B: **NOT AUTHORIZED**

## 1. Executive summary

Phase 10.4C-A3 established owner-provided topology, membership,
Staging R2, and Staging database identity as **PASS
(OWNER-PROVIDED)**; source Risks A and B as **FAIL**; storage and
database boundaries as **PARTIALLY VERIFIED**; and
cross-workspace access as **NOT VERIFIED**.

This phase does **not** re-run those inspections as live tests. It
records which remaining gaps can be closed with owner-gated,
least-invasive evidence, and which proposed negative tests are
**BLOCKED** because they would access Production from Staging.

**Go/no-go for runtime verification: NO-GO.** No live probe is
authorized by this plan. Owner decisions in §7 must be recorded
before any future runtime step. Phase 10.4C-B remains **NOT
AUTHORIZED**.

## 2. Verified repository baseline

Verified this pass (`git fetch origin main`;
`merge-base --is-ancestor d61ea1a origin/main`):

| Field | Value |
| --- | --- |
| Expected baseline | `d61ea1ae3de086fa118eef192bdbba4512dfbcaa` |
| Ancestor check | **ANCESTOR_OK** (exact match of `origin/main`) |
| `origin/main` HEAD | `d61ea1ae3de086fa118eef192bdbba4512dfbcaa` |
| Subject | Merge pull request #94 |
| Commit date | `2026-11-13 10:54:32 +0700` / **13 Nov 2026, 10:54 Asia/Jakarta** |
| Merged by | `mufea` |
| `main` CI after #94 | [43362033546](https://github.com/mufea/docuflow-ai/actions/runs/43362033546) **SUCCESS** — repository CI, **not** isolation |
| PR [#95](https://github.com/mufea/docuflow-ai/pull/95) CI | [43364445655](https://github.com/mufea/docuflow-ai/actions/runs/43364445655) **SUCCESS** (Python `131685423904`, Web `131685423613`; completed **13 Nov 2026, 11:18 Asia/Jakarta**) — repository CI, **not** isolation |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**) |
| Working tree at start | clean at expected baseline after branch create |

Inspected (read-only; not rewritten as historical evidence):

- `docs/IMPLEMENTATION_STATUS.md` (A3 current-status still
  **COMPLETE – UNMERGED** on this SHA; factual git status is
  **MERGED**)
- `docs/reports/PHASE_10_4C_A3_FINAL_ISOLATION_ASSESSMENT.md`
- `docs/reports/PHASE_10_4C_A_RUNTIME_ISOLATION_ASSURANCE.md`
- `docs/reports/PHASE_10_4C_A2R_POST_MERGE_RECONCILIATION.md`
- `docs/reports/PHASE_10_4B_SR7_RUNTIME_ISOLATION_VERIFICATION.md`
  (identity table only)
- `infra/render.staging.yaml` (cleanup startCommand / `fromDatabase`
  / `S3_BUCKET` injection)
- Prior A3 source conclusions for `is_production_bucket()` and
  `src/docuflow/cleanup.py` (not re-executed as live tests)

`src/` was not modified. No live resources were contacted.

## 3. Current isolation status

Carried forward from A3 at merge `d61ea1a`. This plan does **not**
upgrade any row.

| Control / risk | Current classification | Evidence class |
| --- | --- | --- |
| CONTROL-WS Render workspace IDs | **PASS** | OWNER-PROVIDED |
| CONTROL-MEMBERSHIP Staging project All 4 | **PASS** | OWNER-PROVIDED |
| CONTROL-TEAM membership inventory | **PASS** | OWNER-PROVIDED |
| CONTROL-R2 Staging bucket + token scope | **PASS** | OWNER-PROVIDED |
| CONTROL-DB-IDENTITY Staging API + cleanup | **PASS** | OWNER-PROVIDED |
| RISK-A Production bucket helper | **FAIL** | source code |
| RISK-B Cleanup CLI safety | **FAIL** | source code |
| RISK-C Storage boundary | **PARTIALLY VERIFIED** | source + OWNER-PROVIDED |
| RISK-D Database boundary | **PARTIALLY VERIFIED** | source + OWNER-PROVIDED |
| CONTROL-XWS cross-workspace access | **NOT VERIFIED** | no independent proof |
| Overall runtime isolation | **NOT VERIFIED** | mixed; critical gaps remain |
| Phase 10.4C | **NOT COMPLETE** | — |
| Phase 10.4C-B | **NOT AUTHORIZED** | — |

Shared solo-owner Admin on both Hobby workspaces is expected and is
**not** a runtime breach. Distinct workspace IDs are **not** proof
of network, credential, or cross-workspace access isolation.
CI SUCCESS is **not** isolation. MERGED is **not** DEPLOYED.

## 4. Evidence and verification-readiness matrix

| Item | Existing evidence | Evidence class | Proves | Does not prove | Remaining gap | Owner action? |
| --- | --- | --- | --- | --- | --- | --- |
| Production workspace identity | Dashboard chrome `docuflowai`; ID `tea-d84phnqa8673blqsn0`; Hobby | OWNER-PROVIDED | Distinct recorded workspace ID | Independent Render verification; API-key isolation | None for topology; independent check unavailable to this agent | Optional reconfirm if IDs change (OA-0) |
| Staging workspace identity | Dashboard chrome `docuflowai staging`; ID `tea-d9f6cddc9c73dqpab0`; Hobby | OWNER-PROVIDED | Distinct recorded workspace ID | Same as above | Same | Optional reconfirm (OA-0) |
| Admin / membership | One Admin per workspace; no extra members; email not recorded | OWNER-PROVIDED | Inventory at 10:21 Asia/Jakarta | Cross-workspace denial; 2FA/SSO | CONTROL-XWS | OA-1 |
| Staging project/service boundary | Project `DocuflowAI` env Staging All 4: api, web, db, cleanup | OWNER-PROVIDED | Staging-named inventory complete in chrome | Render exclusivity independently; cleanup **run** | `Successful build` ≠ cleanup execution | No live cleanup |
| Production project/service boundary | Project `Docuflow AI` env Production All 6 (api/web Deployed; db Available; cleanup/redis/worker Suspended) | OWNER-PROVIDED | Production-named inventory recorded | That Staging cannot reach those services | CONTROL-XWS | OA-1 |
| Staging database identity | API + cleanup Shell: user `docuflow_staging_db_ikpz_user`; DB `docuflow_staging_db_ikpz` | OWNER-PROVIDED | Both Staging compute services used that identity when captured | Current DSN still matches; Production unreachable from Staging | RISK-D remains injection-only | Do **not** reconnect (OA-5) |
| Production database identity | SR7 owner-provided `docuflow_db_q32a` / `docuflow_db_q32a_user`; service `docuflow-db` | OWNER-PROVIDED (historical) | Distinct **name** from Staging | Live reconnect; that Staging cannot open it | RISK-D / CONTROL-XWS | Optional name-only dashboard reconfirm (OA-4); no DSN |
| Staging R2 bucket + endpoint | `STORAGE_BACKEND=s3`; `S3_BUCKET=docuflowai-staging`; R2 host; key mask `6c01…2307` on API and cleanup `echo` | OWNER-PROVIDED | Live env **names** point at Staging bucket | HeadBucket; exclusive access; Production denial | RISK-C | Do **not** HeadBucket Production |
| Production R2 bucket | Owner-recorded name `docuflowai-documents` | OWNER-PROVIDED | Distinct **name** from Staging | Staging credentials cannot access it | CONTROL-XWS / RISK-A | OA-2 (source); OA-1/OA-4 (token scope). Negative HeadBucket **BLOCKED** |
| Cloudflare Staging token scope | Token named for `docuflowai-staging`; read/write/list; bucket `docuflowai-staging` only | OWNER-PROVIDED | Staging token UI shows one bucket | Production token exclusivity; runtime AWS SigV4 behavior | Complementary Production token screenshot | OA-1 |
| Cleanup execution boundary | Staging cron `python -m docuflow.migrate && python -m docuflow.cleanup`; `CLEANUP_INTERVAL_SECONDS=0`; CLI fail-fast / `--dry-run` added in OA-3 (repository) | REPOSITORY-DERIVED + OWNER-PROVIDED env | Template and env **intent**; unit-tested refusal | Live cron / Shell run; deployed code | RISK-B source **PASS** (OA-3); live **BLOCKED** | OA-3 **PROVIDED**; live cleanup **BLOCKED** |
| Credentials / secret scope | Distinct Access Key ID mask on Staging; secrets not in repo | OWNER-PROVIDED | Staging key is not printed; token UI scoped | Keys cannot call Production; no shared secret | CONTROL-XWS | Never send unmasked secrets (OA-5) |
| Cross-workspace access paths | Same solo Admin; Hobby; no env groups; no app allow-list; Settings inject `DATABASE_URL` / `S3_BUCKET` | OWNER-PROVIDED + REPOSITORY-DERIVED | Shared Admin expected; isolation is env injection | Workspaces cannot reach each other | CONTROL-XWS **NOT VERIFIED** | OA-1; negative probes **BLOCKED** |
| Source Production-bucket helper | `DEFAULT_PRODUCTION_BUCKETS={"docuflow-documents"}`; `is_production_bucket("docuflowai-documents")` is `False` | REPOSITORY-DERIVED | Default helper misses the live Production bucket name | That Staging currently points at Production (it does not, per owner env) | RISK-A **FAIL** | OA-2 (separate code PR if authorized) |
| Independent operational verification | None this agent can obtain (no Render/Cloudflare login) | UNAVAILABLE | — | — | Cannot convert OWNER-PROVIDED to independently verified | Do not impersonate independent audit |

## 5. Proposed safe verification methodology

Future verification is split into gates. **None of these gates is
authorized by this document.** Each live or dashboard capture that
could reveal a secret still requires a fresh owner APPROVE.

### 5.1 Method principles

1. Least privilege: dashboard chrome and name-only identity first.
2. No Production data: no list, get, head, delete, or SQL on
   Production from Staging (or from this agent).
3. No secret material in the repository: no DSN, token, secret key,
   or unmasked Access Key ID.
4. Synthetic evidence only: names, IDs already public in prior
   reports, redacted masks already recorded.
5. PASS/FAIL defined **before** any future test.
6. Stop and rollback: if a proposed step would touch a live
   Production resource, classify **BLOCKED** and stop.
7. Documentation ≠ runtime. Owner screenshot ≠ independent
   verification.

### 5.2 Gates (planned, not executed)

#### G0 — Documentation / ledger hygiene

**Method:** Correct stale **COMPLETE – UNMERGED** after PR #94
merge. No live access.
**PASS:** ledger current-status is **MERGED** with merge SHA
`d61ea1a`.
**FAIL:** not applicable.
**Authorization:** this documentation PR only.

#### G1 — Owner decision on CONTROL-XWS

**Method:** written owner decision, stored in a later docs PR.
Two acceptable outcomes (choose one):

1. Accept in writing that Hobby shared-Admin cross-workspace
   access remains **NOT VERIFIED** and that overall isolation
   therefore stays **NOT VERIFIED**; or
2. Supply complementary **OWNER-PROVIDED** dashboard evidence
   that does not access live data (see OA-1).

**PASS (decision recorded):** a dated owner statement exists in
the repository.
**FAIL:** not used; absence leaves OA-1 **PENDING**.
**Does not convert overall isolation to PASS** by itself.

#### G2 — Complementary Production token bucket list (optional)

**Method:** owner screenshot of the **Production** Cloudflare R2
API-token permission page showing **bucket names only**.
**PASS:** Production token buckets do **not** include
`docuflowai-staging`.
**FAIL:** Production token includes `docuflowai-staging` (shared
scope).
**Stop:** if the screenshot would reveal the token value, Access
Key secret, or extra Access Key digits, do not paste it; retake
with values hidden.
**Evidence class if supplied:** OWNER-PROVIDED (not independent).
**Not authorized now.**

#### G3 — Source Risk A (optional, separate code PR)

**Method:** add `docuflowai-documents` to
`DEFAULT_PRODUCTION_BUCKETS` and a unit test. Local pytest only.
**PASS:** `is_production_bucket("docuflowai-documents") is True`.
**FAIL:** helper still returns False.
**Does not** prove live Staging isolation.
**Not authorized now.** Requires OA-2.

#### G4 — Source Risk B (optional, separate code PR)

**Method:** cleanup CLI fail-fast (reuse production-readiness
errors), reject known Production buckets, fail on empty bucket,
optional `--dry-run` that must not call storage delete.
**PASS:** unit tests show refusal before `run_runtime_cleanup`
mutates; dry-run path does not invoke `storage.delete`.
**FAIL:** CLI still mutates with default/Production bucket.
**Live cleanup remains BLOCKED** even after a source fix until a
later owner authorization names Staging-only dry-run.
**Authorized and implemented** in this OA-3 source PR. See §12.
Live cleanup is still **BLOCKED**.

#### G5 — Negative Production storage or database access — **BLOCKED**

**Proposed test (rejected):** from Staging credentials, HeadBucket
or ListObjects on `docuflowai-documents`, or open Production
`DATABASE_URL`.
**Why BLOCKED:** it accesses a Production resource from Staging
(or from the agent). A 403 is still a live Production probe. This
phase forbids Production probes, object enumeration, and
cross-workspace resource access.
**No substitute live test is invented** to obtain a PASS.

#### G6 — Cleanup execution — **BLOCKED**

**Proposed test (rejected):** run `python -m docuflow.cleanup` on
Staging or Production.
**Why BLOCKED:** live cleanup mutates jobs and storage.
`--dry-run` now exists in source (OA-3) but was **not** invoked
on Render. `Successful build` is not a run. A merged code PR does
not authorize live cleanup.
**No live cleanup.**

#### G7 — Phase 10.4C-B functional Staging tests — **NOT AUTHORIZED**

See §8. Not a verification method in this phase.

### 5.3 Expected future evidence classes

| Gate | If later completed | Class |
| --- | --- | --- |
| G0 | ledger MERGED | repository documentation |
| G1 | owner written decision | OWNER-PROVIDED decision |
| G2 | token bucket screenshot | OWNER-PROVIDED |
| G3 / G4 | source + unit tests | REPOSITORY-DERIVED |
| G5 / G6 | not to be run | **BLOCKED** |
| Independent Render/Cloudflare login by this agent | unavailable | UNAVAILABLE |

## 6. Explicit prohibitions and stop conditions

This phase did **not**, and any future gate must **not** without a
new explicit owner APPROVE that names the action:

- Execute Shell on Render Production or Staging.
- Perform live API, database, Redis, worker, or storage probes.
- Attempt cross-workspace resource access.
- Read or enumerate Production data or objects.
- Execute cleanup or test cleanup execution.
- Run migrations, restores, exports, backups, or deletions.
- Change Render configuration, env, access policies, or memberships.
- Rotate, retrieve, print, or expose secrets, DSNs, or tokens.
- Deploy or restart any service.
- Modify application code in this planning PR.
- Authorize Phase 10.4C-B.

**Stop immediately if:**

- A proposed step requires a Production DSN, token, or object key.
- A screenshot would disclose a secret; retake, do not commit it.
- Staging and Production resource names become ambiguous.
- A test cannot be distinguished from a Production write.
- Owner authorization is missing, generic, or implied by merge.

**Rollback boundary:** this PR changes documentation only. There is
no infrastructure rollback because nothing was changed.

Safety declaration for **this** phase:

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
- Phase 10.4C-B was not authorized or executed.

## 7. Owner action register

All items **PENDING** unless noted. Do not send passwords, tokens,
DSNs, or unmasked credentials.

| ID | Decision or evidence required | Why | Safe way to provide | Must remain untouched | Status | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| OA-0 | Optional: confirm workspace IDs unchanged | Detect topology drift | Settings screenshot showing IDs only | Env, DNS, membership | PENDING (optional; current IDs already recorded) | G0/G1 |
| OA-1 | Written choice: (a) accept CONTROL-XWS as **NOT VERIFIED**, or (b) complementary Production token bucket-name screenshot proving it does not list `docuflowai-staging` | Overall isolation cannot become PASS while CONTROL-XWS is open unless owner accepts the residual | Dated written statement in chat/PR, **or** Cloudflare permission UI with token value hidden | Tokens, keys, buckets, Render env | **PROVIDED** — Option A; see §10 | G1 |
| OA-2 | Authorize or decline a **separate** source PR to default-flag `docuflowai-documents` | RISK-A default helper omitted the live Production bucket name | “APPROVE OA-2” or “DECLINE OA-2” in writing | Live env; no deploy from the code PR until separately approved | **PROVIDED** — APPROVE; see §11 | G3 |
| OA-3 | Authorize or decline a **separate** source PR for cleanup fail-fast / bucket reject / dry-run | RISK-B remains **FAIL** until source fix | “APPROVE OA-3” or “DECLINE OA-3” | No live cleanup; no Production bucket | **PROVIDED** — APPROVE; see §12 | G4 |
| OA-4 | Optional: Production dashboard name-only reconfirm of Postgres database **name** and `S3_BUCKET` **name** | Strengthens RISK-C/D name distinctness without connecting | Cropped service Info / env **name** rows; no DSN, no secret | Databases, objects, cleanup | PENDING (optional) | identity only |
| OA-5 | Standing prohibition: no live probes, Shell, SQL, HeadBucket, cleanup, deploy, or secret paste unless a later message names the exact action and says APPROVE | Prevent implied authorization | Do nothing | All live resources | **PENDING** (in force as prohibition) | all live gates |
| OA-6 | Do **not** authorize Phase 10.4C-B until this plan and A3 classifications are accepted | Stage B is functional Staging testing, not isolation closure | Explicit “APPROVE Phase 10.4C-B” naming allowed Staging tests | Production; cleanup; migrations unless named | **PENDING** — currently **NOT AUTHORIZED** | G7 |

## 8. Phase 10.4C-B authorization prerequisites

Phase 10.4C-B stays **NOT AUTHORIZED** until **all** of the
following are true:

1. Owner has recorded OA-1 (accept residual CONTROL-XWS **or**
   supply complementary token-scope evidence). **Recorded 13 Nov
   2026, 13:12 Asia/Jakarta: Option A. See §10.**
2. Owner has recorded OA-2 and OA-3 as APPROVE or DECLINE.
   **OA-2 APPROVE recorded 13 Nov 2026, 13:50 Asia/Jakarta; see
   §11.** **OA-3 APPROVE recorded 13 Nov 2026, 13:57
   Asia/Jakarta; see §12.** Recording APPROVE is not a live
   cleanup authorization.
3. Owner sends a separate message that names Phase 10.4C-B and
   the exact Staging tests permitted.
4. Those tests remain Staging-only: no Production HTTP, Shell,
   SQL, storage, or cleanup unless separately named.
5. Overall runtime isolation is still labeled **NOT VERIFIED**
   unless new **authorized** runtime evidence supports a change.
   Topology PASS plus this plan do **not** satisfy that.

Merging this planning PR does **not** satisfy items 1–4.

## 9. Final go/no-go recommendation

| Question | Recommendation |
| --- | --- |
| Is the verification **plan** ready for owner review? | **YES** |
| Is any runtime isolation probe authorized now? | **NO-GO** |
| Can CONTROL-XWS be proven without Production access? | **NO** — negative tests are **BLOCKED**; OA-1 Option A **PROVIDED** (residual accepted) |
| Can RISK-A / RISK-B be closed without code changes? | **NO** — they are source defects; live tests are the wrong tool |
| Overall runtime isolation | **NOT VERIFIED** |
| Phase 10.4C complete? | **NO** |
| Phase 10.4C-B | **NOT AUTHORIZED** |

Stop after this planning deliverable. Wait for explicit owner
authorization before any runtime verification.

## 10. OA-1 owner decision — Option A **PROVIDED**

Time: **13 Nov 2026, 13:12 Asia/Jakarta (WIB)**. Documentation only.
Owner / Approver: EDY ALAMSAH (message recorded in this repository).
Baseline at recording: `origin/main`
`2d753e6b38de50bcb68e4ccb4b258ea407c708ca` (Merge PR #95).
PR [#96](https://github.com/mufea/docuflow-ai/pull/96) repository CI:
[43377234803](https://github.com/mufea/docuflow-ai/actions/runs/43377234803)
**SUCCESS** (Python `131726469791`, Web `131726469400`; completed
**13 Nov 2026, 13:15 Asia/Jakarta**) — repository CI, **not** isolation.

Owner statement (recorded, not paraphrased as a stronger claim):

- OA-1: **ACCEPT OPTION A**.
- CONTROL-XWS (cross-workspace access isolation) is accepted as
  **NOT VERIFIED**.
- No additional Production access test, Cloudflare token
  inspection, or live probe is authorized.
- Overall runtime isolation remains **NOT VERIFIED**.

Gate G1 is **closed as a decision record**. Gate G2 is **not**
taken. CONTROL-XWS classification is **unchanged**: **NOT
VERIFIED**. This acceptance does **not** convert overall isolation
to PASS. It does **not** authorize OA-2, OA-3, live probes, or
Phase 10.4C-B.

| Label | Result |
| --- | --- |
| OA-1 | **PROVIDED** (Option A) |
| CONTROL-XWS | **NOT VERIFIED** (accepted residual) |
| G2 Production token screenshot | **NOT AUTHORIZED** |
| G5 / G6 live negative tests | **BLOCKED** (unchanged) |
| OA-2 / OA-3 | **PENDING** |
| OA-5 live-probe prohibition | in force |
| OA-6 / Phase 10.4C-B | **NOT AUTHORIZED** |
| Overall runtime isolation | **NOT VERIFIED** |
| Phase 10.4C | **NOT COMPLETE** |

Safety declaration for this recording:

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
- Phase 10.4C-B was not authorized or executed.

## 11. OA-2 source fix — Production bucket helper

Time: **13 Nov 2026, 13:50 Asia/Jakarta (WIB)**. Owner EDY ALAMSAH
authorized OA-2. Source and unit tests only. No live env, Render
change, deploy, or probe.

Change: `DEFAULT_PRODUCTION_BUCKETS` now includes both the legacy
Settings default `docuflow-documents` and the owner-recorded live
Production bucket `docuflowai-documents`. `is_production_bucket()`
and `is_forbidden_live_test_bucket()` therefore default-flag the
live Production name. Call sites at OA-2 merge were confined to
`staging_checks.py` (preflight / `validate_staging_configuration`).
OA-3 later wired the helper into cleanup validation (see §12).

Preserved: empty-name `False`; case normalization; optional
`production_bucket` kwarg; Staging names `docuflow-staging` and
`docuflowai-staging` remain non-production.

Local tests (SQLite `DATABASE_URL`; no live resources):
`test_production_resource_reuse_is_detected`,
`test_staging_config_rejects_production_reuse_and_rq`, and
`test_phase910_provisioning.py` — **7 passed**.
PR [#97](https://github.com/mufea/docuflow-ai/pull/97) repository CI:
[43381680153](https://github.com/mufea/docuflow-ai/actions/runs/43381680153)
**SUCCESS** (Python `131740643955`, Web `131740643750`; completed
**13 Nov 2026, 13:54 Asia/Jakarta**) — repository CI, **not**
isolation and **not** a deploy.

| Label | Result |
| --- | --- |
| OA-2 | **PROVIDED** (APPROVE; this source PR) |
| RISK-A default helper | **PASS** (repository; unit tests) |
| RISK-B cleanup CLI | **FAIL** at OA-2 merge; source **PASS** after OA-3 (§12). Live cleanup **BLOCKED** |
| Overall runtime isolation | **NOT VERIFIED** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Deploy of this helper | **NOT AUTHORIZED** by this PR |

A3 historical **FAIL** at SHA `e62962b` / `d61ea1a` is preserved.
This section records the later source closure of the default
identifier only.

Safety declaration for OA-2 implementation:

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
- Phase 10.4C-B was not authorized or executed.

## 12. OA-3 source fix — cleanup CLI safety hardening

Time: **13 Nov 2026, 13:57 Asia/Jakarta (WIB)**. Owner EDY ALAMSAH
authorized OA-3. Source and local unit tests only. No Render Shell,
live cleanup, database/storage access, migration, deploy, or
Production/Staging configuration change.

A merged code PR does **not** authorize live cleanup execution.

### Change

`src/docuflow/cleanup.py`:

- Fail-fast `validate_cleanup_configuration()`:
  production-readiness errors when `DOCUFLOW_ENV` is production
  (Blueprint value for both Staging and Production);
  empty `S3_BUCKET` rejected; S3 keys required for `s3`.
- Known Production buckets (`docuflow-documents`,
  `docuflowai-documents` via `is_production_bucket()`) are
  **refused only in an isolated/Staging context**
  (`RENDER_SERVICE_NAME`, public API/web host, or database
  identity containing `staging` or `test`). Production cron
  `docuflow-cleanup` with `docuflowai-documents` still validates.
- `--dry-run` validates and exits. It does not create an engine,
  open a session, build storage, call `run_runtime_cleanup`, or
  invoke `storage.delete`.
- Unsafe configuration raises `CleanupConfigError` before any
  factory; `main()` returns `1`.

`src/docuflow/jobs/scheduler.py`: in-process
`CleanupScheduler.run_once` uses the same validator and returns
without opening a session when configuration is unsafe.

Blueprints, startCommand, env, and Render services were **not**
changed.

### Call sites and deployment entry points inspected (read-only)

| Entry | Path | OA-3 effect |
| --- | --- | --- |
| Module CLI | `python -m docuflow.cleanup` → `main()` | fail-fast + `--dry-run` |
| Console script | `docuflow-cleanup` → `docuflow.cleanup:main` (`pyproject.toml`) | same `main()` |
| Production cron | `infra/render.yaml` `docuflow-cleanup` `python -m docuflow.migrate && python -m docuflow.cleanup` | **unchanged**; Production bucket still allowed |
| Staging cron | `infra/render.staging.yaml` `docuflow-staging-cleanup` same startCommand | **unchanged**; Production bucket refused after deploy of this code |
| API in-process | `src/docuflow/main.py` `CleanupScheduler` (`CLEANUP_INTERVAL_SECONDS=0` in both Blueprints) | shares validator |
| Worker in-process | `src/docuflow/worker.py` `CleanupScheduler` (no Staging worker; Production worker suspended) | shares validator |
| `run_runtime_cleanup` | `src/docuflow/jobs/retention.py`; tests only besides CLI/scheduler | mutating core; not invoked by `--dry-run` |
| GitHub Actions | `.github/` | **no** cleanup job |

### Local tests

SQLite `DATABASE_URL`; `DOCUFLOW_ENV=test`; no live resources.
`tests/test_phase104c_cleanup_cli.py` plus
`tests/test_phase91_cleanup.py` — **20 passed** (11 new + 9
existing). Dry-run test asserts `storage_factory`,
`engine_factory`, `run_cleanup`, and `storage.delete` are never
called.

### Residual

Source RISK-B is closed in the repository. Runtime isolation
remains **NOT VERIFIED**. Deploy of this code is **NOT
AUTHORIZED**. Live `--dry-run` or mutating cleanup on Staging or
Production is **NOT AUTHORIZED**. Isolation still depends on env
injection (`S3_BUCKET`, `DATABASE_URL`, Render service name).
Phase 10.4C-B remains **NOT AUTHORIZED**.

| Label | Result |
| --- | --- |
| OA-3 | **PROVIDED** (APPROVE; this source PR) |
| RISK-B cleanup CLI | **PASS** (repository; unit tests) |
| RISK-A default helper | **PASS** (repository; OA-2 merged `cf0d615`) |
| Live cleanup | **BLOCKED** / **NOT AUTHORIZED** |
| Overall runtime isolation | **NOT VERIFIED** |
| Phase 10.4C-B | **NOT AUTHORIZED** |
| Deploy of this CLI | **NOT AUTHORIZED** by this PR |

A3 historical RISK-B **FAIL** at SHA `e62962b` / `d61ea1a` is
preserved. This section records the later source closure.

Safety declaration for OA-3 implementation:

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
- Phase 10.4C-B was not authorized or executed.
