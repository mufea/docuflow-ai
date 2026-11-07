# Phase 9.10C — Staging final verification and security isolation

Verification and evidence only. No application-code changes.

Status labels are never combined. Skipped or blocked checks are not PASS.

## 1. Repository baseline

| Item | Value |
| --- | --- |
| Repository | https://github.com/mufea/docuflow-ai |
| `origin/main` | `5e9a6b4f8270b9bb486b675b1aca2413cd4e69e4` |
| Main subject | Merge pull request #18 from `cursor/phase-9-10b-mutating-smoke-evidence-8f43` |
| PR #18 | **MERGED** 7 Nov 2026, 09:49 Asia/Jakarta (`mergedAt` 2026-11-07T02:49:32Z) |
| Evidence commit | `8aa95c5` |
| Working tree at audit | Clean on previous evidence branch; this report is on `cursor/phase-9-10c-final-verification-8f43` |
| Report timestamp | 7 Nov 2026, 10:03 Asia/Jakarta (WIB) |

Historical 9.10A/B results are treated as owner/agent evidence, not re-executed mutating tests.

## 2. Staging architecture (unchanged)

| Component | Status |
| --- | --- |
| API | `https://docuflow-staging-api.onrender.com` |
| Web | `https://docuflow-staging-web.onrender.com` |
| Database | `docuflow_staging_db` (owner-reported name) |
| Storage | S3-compatible staging bucket; `/ready` storage true |
| Broker | `inline` |
| Redis / worker | Absent (expected) |

## 3. Security isolation audit (code + local tests)

Server-side ownership:

- `DocumentService.get_owned` loads by id, 404 if missing/deleted, **403** if `user_id` mismatch (admin role may bypass).
- Download, GET, and DELETE all call `get_owned`.
- `JobService.create` calls `get_owned` for every input document.
- `JobService.get_owned` uses the same 404/403 pattern.
- Job runner refuses documents whose `user_id` does not match the job owner.
- Unauthenticated routes using `require_user` raise `AuthenticationError` **401**.

Policy: other-user access is **403**, not 404 (document existence is distinguishable).

Security matrix (expected vs evidence):

| Scenario | Expected | Evidence |
| --- | --- | --- |
| User A accesses own document | 200 | Local tests + owner mutating upload PASS |
| User B GET User A document | 403 | **Locally tested** `test_cross_user_document_access_denied` |
| User B download User A document | 403 | **Locally tested** (jobs + phase 9.5 tests) |
| User B delete User A document | 403 | **Locally tested** `test_user_cannot_purge_another_users_document` |
| User B extract_text on User A document | 403 | **Locally tested** |
| Unauthenticated `/v1/auth/me` | 401 | **Locally tested** `test_register_login_me_logout` |
| Invalid / deleted document id | 404 | Existing cleanup tests |
| Live staging User B vs User A | 403 | **BLOCKED** — `STAGING_SMOKE_SECOND_EMAIL` / `PASSWORD` UNSET. No account created. |

Local command (7 Nov 2026, 10:03 Asia/Jakarta):

```
uv run pytest -q \
  tests/test_jobs_and_security.py::test_cross_user_document_access_denied \
  tests/test_phase95_readiness.py::test_cross_user_cannot_download_another_users_file \
  tests/test_phase91_cleanup.py::test_user_cannot_purge_another_users_document \
  tests/test_phase9_integrity.py::test_cross_user_job_access_denied \
  tests/test_auth_api.py::test_register_login_me_logout
# 5 passed in 1.74s, exit 0
```

A passing local unit test does **not** prove live staging isolation.

## 4. Hosted migrate-verify

`scripts/staging_migrate_verify.py` is inspect-then-optionally-upgrade:

- Gate: `STAGING_MIGRATE_VERIFY=1` or exit 2, no DB contact.
- Requires `DATABASE_URL` and `STAGING_DATABASE_CONFIRM`.
- Refuses SQLite and production-like identity.
- Applies Alembic only if `STAGING_MIGRATE=1`.
- Expected head: `0003_cost_efficient_reliability`.

This environment: `STAGING_MIGRATE_VERIFY` UNSET, `DATABASE_URL` UNSET. Staging Postgres `ipAllowList: []`.

```
uv run python scripts/staging_migrate_verify.py
# NOT EXECUTED: STAGING_MIGRATE_VERIFY is not 1. No database was contacted.
# exit 2
```

Hosted migrate-verify: **BLOCKED**. Upgrade was **not** requested and **not** run.

## 5. Staging HTTP (non-mutating, this environment)

Mutating smoke was **not** repeated (already owner PASS in 9.10B).

```
STAGING_API_URL=https://docuflow-staging-api.onrender.com
STAGING_HOST_CONFIRM=docuflow-staging-api.onrender.com
STAGING_WEB_URL=https://docuflow-staging-web.onrender.com
STAGING_SMOKE_TIMEOUT=90
uv run python scripts/staging_smoke.py
# PASS /health, /ready broker=inline database/storage true, frontend HTTP 200
# SKIPPED mutating checks (STAGING_SMOKE_MUTATIONS is not 1)
# exit 0
```

Provider tests: **not re-run** (`TEST_S3_*` UNSET). Owner-run `pytest -m provider` PASS remains 6 Nov 2026 evidence.

## 6. Verification results

| Area | Result | Evidence |
| --- | --- | --- |
| Repository audit | PASS | `origin/main` `5e9a6b4`; PR #18 merged |
| Non-mutating smoke | PASS | this environment, 10:03 Asia/Jakarta |
| Mutating smoke | PASS | owner-run 9.10B; not repeated |
| Provider tests | PROVIDER VERIFIED | owner-run; not repeated here |
| Authentication | PASS | owner mutating login + `/me`; local 401 after logout |
| Cross-user isolation (local) | LOCALLY TESTED | 5 pytest PASS |
| Cross-user isolation (staging) | BLOCKED | second staging account unset |
| Hosted migrate-verify | BLOCKED | no staging DSN; migrate gate unset |
| Database readiness | PASS | `/ready` `database=true` (connectivity, not Alembic head) |
| Storage readiness | PASS | `/ready` `storage=true` |
| Frontend | PASS | HTTP 200 |
| API readiness | PASS | `/ready` `broker=inline` |
| Cleanup | PASS | owner smoke DELETE HTTP 200; cron not independently run |

## 7. Code changes

No application code modified. No tests added. Documentation-only evidence for this phase.

## 8. Security findings

Confirmed vulnerabilities: **none** from this audit.

Residual risks (not treated as defects for a code change):

- Other-user access returns 403 (existence leak vs 404). Existing policy.
- `role=admin` may access any document/job. Live account role not independently verified.
- Download is HTTP 302 to a time-limited signed URL; the smoke does not checksum the body.
- Live staging cross-user isolation is **not** proven.

## 9. Status

Chosen 9.10C outcome: **STAGING VERIFICATION INCOMPLETE**.

Lifecycle in staging works (**STAGING FUNCTIONAL VERIFIED: YES**). **STAGING VERIFIED** is withheld because live cross-user isolation and hosted migrate-verify remain **BLOCKED**.

| Status | Value |
| --- | --- |
| STAGING PROVISIONED | YES |
| PROVIDER VERIFIED | YES |
| STAGING FUNCTIONAL VERIFIED | YES |
| STAGING VERIFIED | **NO** |
| PRODUCTION DEPLOYED | **NO** |
| PRODUCTION VERIFIED | **NO** |
| PRODUCTION AUTHORIZED | **NO** |

## 10. Remaining owner actions

1. Optional live cross-user: set `STAGING_SMOKE_MUTATIONS=1` plus a **second** dedicated staging user (`STAGING_SMOKE_SECOND_EMAIL` / `PASSWORD`) on the owner machine. Do not paste passwords into chat. Then re-run `scripts/staging_smoke.py`.
2. Hosted migrate-verify from Render shell on `docuflow-staging-api` (or a temporary IP allowlist): `STAGING_MIGRATE_VERIFY=1`, `STAGING_DATABASE_CONFIRM=docuflow_staging_db`, using the injected staging `DATABASE_URL`. Do **not** set `STAGING_MIGRATE=1` unless current revision is pending and you explicitly approve an upgrade. Never against production.
3. Production remains unauthorized.

## 11. Next recommendation

Smallest next step: owner-run hosted migrate-verify (read-only inspect) from the staging API shell. That is the remaining schema gate. Cross-user staging is the remaining isolation gate.
