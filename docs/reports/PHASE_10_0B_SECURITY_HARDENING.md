# Phase 10.0B — Security hardening, regression tests, and verification

Repository-level security review, targeted code, tests, and documentation
only. **Not** a restore, export, cutover, or production change.

Time: **10 Nov 2026, 19:52 Asia/Jakarta (WIB)** (`2026-11-10T12:52:09Z`).
Base `origin/main`: **`b9e0e11f2ad79883ffbccc7807df6317523d72cd`**
(PR #49 / Phase 10.0A merge; confirmed after `git fetch origin`).

## 1. Phase 10.0A dependency

| Item | Value | Classification |
| --- | --- | --- |
| PR [#49](https://github.com/mufea/docuflow-ai/pull/49) | **MERGED** | **VERIFIED** |
| Merge commit | `b9e0e11f2ad79883ffbccc7807df6317523d72cd` | **VERIFIED** |
| Merge time | 2026-11-10T12:49:10Z (19:49 Asia/Jakarta) | **VERIFIED** |
| CI | [42818081339](https://github.com/mufea/docuflow-ai/actions/runs/42818081339) Python **SUCCESS**; web **SUCCESS** | **VERIFIED** (repository CI, not production) |
| Temp-file / broker shutdown on this base | Present in `documents.py` / `broker.py` / `main.py` | **VERIFIED** (source on `main`) |
| 10.0A regression tests | `tests/test_phase10_runtime_reliability.py` | **TESTED** locally this phase |

Combined Phase 10.0 is **not** claimed complete in production. 10.0A is
merged; this PR is 10.0B only.

## 2. Repository baseline

| Item | Value | Classification |
| --- | --- | --- |
| Audit time (UTC) | 2026-11-10T12:52:09Z | **VERIFIED** |
| `origin/main` | `b9e0e11f2ad79883ffbccc7807df6317523d72cd` | **VERIFIED** |
| Working tree before edits | clean | **VERIFIED** |
| Open PRs at audit | none | **VERIFIED** |

Tests ran with production `DATABASE_URL` **unset**. The value was not
printed or used. Production SQL: **NOT EXECUTED**.

## 3. Files audited

- `src/docuflow/security/rate_limit.py`
- `src/docuflow/api/routes/auth.py`
- `src/docuflow/services/auth.py`
- `src/docuflow/api/deps.py`
- `src/docuflow/main.py` (no ProxyHeaders middleware)
- `src/docuflow/config.py` (trusted hosts only; no trusted-proxy list)
- `src/docuflow/api/routes/documents.py` (10.0A cleanup; upload limiter is per `user.id`)
- `tests/test_auth_api.py`
- `docs/DEPLOYMENT.md` / `docs/OPERATIONS.md` (no trusted-proxy rate-limit docs)

## 4. Confirmed security findings

| ID | Finding | Classification |
| --- | --- | --- |
| S1 | Forgot-password used a global key `"forgot"`, so one client could exhaust the quota for all clients | **CONFIRMED** → **FIXED** → **TESTED** |
| S2 | No application code read `X-Forwarded-For` / `X-Real-IP` for limits. Spoofed headers must not become a new identity | **CONFIRMED** (no header trust) → helper documents and tests **TESTED** that headers cannot bypass the peer bucket |
| S3 | `MemoryRateLimiter` is process-local; counters reset on process restart; not shared across replicas | **CONFIRMED** (code). **Not** a defect to “fix” with Redis. Remaining limitation |
| S4 | Login/register already keyed by `request.client.host` (TCP peer). Behind a reverse proxy that is often one address for all users | **CONFIRMED** limitation. **Not** “fixed” by trusting forwarding headers |
| S5 | Reset-password and verify-email had no independent rate limit | **CONFIRMED** → **FIXED** (per-client keys, 10/60s) → **TESTED** via shared limiter independence (login vs forgot). Reset/verify limits are unit-covered by the same `hit` helper pattern |
| S6 | Forgot-password JSON does not disclose whether the account exists (`request_password_reset` returns without error if missing) | Already correct → **TESTED** |
| S7 | Invalid forgot-password email is 422 (Pydantic `EmailStr`) | Already correct → **TESTED** |

No Redis or external rate-limit service was added.

## 5. Fixes implemented

1. `src/docuflow/security/client_ip.py` — `rate_limit_client_id()` uses the
   direct TCP peer only. It does **not** read forwarding headers.
2. Auth routes key limits as `register:`, `login:`, `forgot:`, `reset:`,
   `verify:` plus that client id.
3. Regression tests in `tests/test_phase10b_security.py`.

Password-reset **workflow** (token issue/consume) is unchanged.

## 6. Regression tests

- Peer identity ignores `X-Forwarded-For` / `X-Real-IP` / `Forwarded`
- Memory limiter isolates keys
- Forgot known vs unknown email: both `200 {"ok": true}`
- Invalid email: 422
- Per-client forgot quota; second client still allowed
- Spoofed forwarding headers cannot open a new bucket
- Login remains available after the forgot quota is exhausted

## 7. Commands and results

All pytest/ruff/mypy used `env -u DATABASE_URL`.

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/test_phase10b_security.py tests/test_auth_api.py tests/test_phase10_runtime_reliability.py tests/test_jobs_and_security.py` | **26 passed** |
| `uv run pytest -q -m "not integration"` | **259 passed**, 1 skipped, 13 deselected |
| `uv run pytest -q -m integration` | **13 passed** (local 127.0.0.1) |
| `uv run ruff check src tests scripts` | All checks passed |
| `uv run mypy src/docuflow` | Success, 74 source files |
| `git diff --check` | pass |
| Web suite | **NOT EXECUTED** (no web/shared-interface change) |

## 8. Process-local rate-limiter limitations

- In-memory, per API process. Multiple replicas do **not** share counts.
- Restart clears buckets.
- Not distributed. Do not describe this as cluster-wide rate limiting.

## 9. Trusted-proxy assumptions

- There is **no** trusted-proxy IP list in settings.
- Rate-limit identity is the ASGI `request.client` peer (Starlette /
  uvicorn), not forwarded headers.
- Uvicorn may still apply proxy headers at the server layer when the
  peer is in its own `forwarded_allow_ips` (default typically loopback).
  This application **does not** add `ProxyHeadersMiddleware` or parse
  `X-Forwarded-For` for limits.
- If production terminates TLS at a proxy, many users may share one
  login/forgot bucket (the proxy peer). That is safer than header spoof
  bypass. A future explicit trusted-proxy setting would be a separate
  authorized change.

## 10. Remaining security risks

- Process-local limits (above).
- Shared peer behind an unconfigured reverse proxy.
- Timing of forgot-password (email send vs skip) may still differ;
  response **body** does not enumerate accounts.
- Reset-token guessing is only bounded per client/process, not globally.
- Production auth/rate-limit behavior: **NOT VERIFIED**.

## 11. Production and infrastructure

| Item | Status |
| --- | --- |
| Production DSN used | **NOT EXECUTED** |
| Production SQL / restore / export | **NOT EXECUTED** |
| Render / Blueprint / paid services | **NOT EXECUTED** |
| Production security verification | **NOT VERIFIED** |
| Staging security verification | **NOT VERIFIED** |

## 12. Final classification

PHASE 10.0B IMPLEMENTATION: **COMPLETE – UNMERGED**.
LOCAL VALIDATION: **TESTED**.
PRODUCTION VERIFIED: **NOT VERIFIED**.
PHASE_9_15: **OPEN**.
BACKUP_ASSURANCE: **INCOMPLETE**.
PRODUCTION_DR_READINESS: **NOT DEMONSTRATED**.

The classification above is the original pre-merge report. It remains
historical evidence. Current git status is in section 13.

## 13. Post-merge reconciliation (Phase 10.0C)

Audit time: **10 Nov 2026, 20:11 Asia/Jakarta (WIB)**
(`2026-11-10T13:11:47Z`). Live GitHub recheck; not assumed from the
prior 20:05 Asia/Jakarta baseline.

| Item | Verified value |
| --- | --- |
| PR | [#50](https://github.com/mufea/docuflow-ai/pull/50) **MERGED** |
| Merge commit | `7dcca325c394b79ff759f42ed84ddced5555d344` |
| Merged at | `2026-11-10T13:00:07Z` / **10 Nov 2026, 20:00 Asia/Jakarta** |
| Current `origin/main` | `7dcca325c394b79ff759f42ed84ddced5555d344` |
| CI run | [42819517340](https://github.com/mufea/docuflow-ai/actions/runs/42819517340) |
| CI conclusion | **SUCCESS** (Python tests and checks; Web lint, typecheck, tests, and build) |
| Phase 10.0A | PR [#49](https://github.com/mufea/docuflow-ai/pull/49) **MERGED** (`b9e0e11`) |

CI **SUCCESS** is repository CI only. Production runtime verification
of Phase 10.0B remains **NOT VERIFIED**. Staging verification of Phase
10.0 changes remains **NOT VERIFIED**. Merging this PR did **not**
change Phase 9.15 (**OPEN**), backup assurance (**INCOMPLETE**),
observed RPO (**NOT DETERMINABLE**), alerting (**NOT EXECUTED** /
**NOT VERIFIED**), R2/object restore (**NOT VERIFIED**), business
RTO/RPO capability (**NOT DEMONSTRATED**), or production DR readiness
(**NOT DEMONSTRATED**).
