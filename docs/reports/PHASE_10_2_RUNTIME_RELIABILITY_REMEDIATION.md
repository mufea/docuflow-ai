# Phase 10.2 — Runtime reliability and security gap remediation

Implements approved R1–R3 from Phase 10.1. Does **not** implement SIGKILL
job recovery, result-commit ordering, Redis/RQ, or proxy-aware identity.

Time: **10 Nov 2026, 21:12 Asia/Jakarta (WIB)**.

## 1. Baseline

| Item | Value |
| --- | --- |
| `origin/main` | `459c21d80f4d1d47f2f7c96212765bd08c2ff44d` (PR #53 merge) |
| Branch | `feat/phase-10-2-runtime-reliability-remediation` |
| Implementation commit | `687bf644f6e1638eb6c15f2b000d2dffa518c82d` |
| Production / staging runtime | **NOT VERIFIED** |
| Deploy | **NOT EXECUTED** |

## 2. Files changed

- `src/docuflow/security/rate_limit.py`
- `tests/test_phase10b_security.py`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY.md`
- `docs/OPERATIONS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/reports/PHASE_10_2_RUNTIME_RELIABILITY_REMEDIATION.md`

No Render Blueprint, env, migration, or application route-threshold changes.

## 3. R1 — Route-level HTTP 429 tests

Reset-password (10/60s) and verify-email (10/60s) now have deterministic
`TestClient` tests, following the forgot-password pattern:

- Invalid tokens that pass schema return **401** under the limit (no real
  email, no valid secrets).
- The 11th request from the same peer returns **429**
  `{error: rate_limited, message: Too many requests. Try again shortly.}`.
- A second peer is not blocked.
- Reset and verify quotas are independent.
- Rotating `X-Forwarded-For` / `X-Real-IP` does not open a new bucket.

Forgot-password coverage is unchanged and still passing. Thresholds were
not modified.

## 4. R2 — Empty bucket eviction

`MemoryRateLimiter` no longer uses `defaultdict`. Each `hit` holds the
existing `threading.Lock`, drops expired timestamps on every stored key
using that key’s last `window_seconds`, and deletes empty buckets
(including their window metadata). The current key is then recorded.

- Active buckets inside their window are kept.
- An idle key is removed when another `hit` runs after its window.
- Reusing an evicted key starts a new window and still honors `limit`.
- Concurrent `hit` calls serialize on the same lock; a 80-thread test
  shows exactly `limit` recorded events.

Identity remains the caller-supplied key (auth still uses TCP peer).
No Redis. No background sweeper.

## 5. R3 — `FORWARDED_ALLOW_IPS`

Documented in `docs/DEPLOYMENT.md` (new section), with pointers from
`docs/SECURITY.md` and `docs/OPERATIONS.md`.

Application code still does not parse forwarding headers. Uvicorn may
rewrite `request.client` only for peers in `FORWARDED_ALLOW_IPS`
(default `127.0.0.1` if unset). **Do not set `FORWARDED_ALLOW_IPS=*`.**
No Render proxy CIDRs are invented. No start command or dashboard env
was changed. Documenting the variable does **not** make limits
proxy-aware. Live dashboard values remain **NOT VERIFIED**.

## 6. Tests executed

All with `env -u DATABASE_URL`. Isolated sqlite fixtures. No real email.

| Stage | Command | Result |
| --- | --- | --- |
| A focused | `uv run pytest -q tests/test_phase10b_security.py` | **PASS** 16 passed |
| B regression | `uv run pytest -q tests/test_phase10b_security.py tests/test_auth_api.py tests/test_phase10_runtime_reliability.py tests/test_jobs_and_security.py` | **PASS** 34 passed |
| C unit suite | `uv run pytest -q -m "not integration"` | **PASS** 267 passed, 1 skipped, 13 deselected |
| C lint | `uv run ruff check src tests scripts` | **PASS** |
| C typecheck | `uv run mypy src/docuflow` | **PASS** (74 files) |
| C web lint/typecheck/test/build | — | **NOT RUN** (no web files changed) |
| C integration | `pytest -m integration` | **NOT RUN** locally (deselected; CI job runs them) |
| `git diff --check` | — | **PASS** |

Local PASS is not GitHub Actions. GitHub Actions: see the PR checks after
push (**NOT RUN** at the time this file was written).

## 7. Remaining risks (not fixed)

- SIGKILL still leaves `processing` jobs until stale cleanup
  (`JOB_STALE_MINUTES`, default 90).
- `store_result` can still commit documents before the job row is
  `completed` (orphans + later refund).
- Rate limiter remains process-local; not shared across replicas.
- Reverse-proxy clients may share one TCP peer bucket.
- Production `FORWARDED_ALLOW_IPS` dashboard value **NOT VERIFIED**.
- Phase 9.15 **OPEN**; backup assurance **INCOMPLETE**; production DR
  **NOT DEMONSTRATED**.
- Phase 10.0/10.2 staging and production runtime **NOT VERIFIED**.

## 8. Safety

- Production accessed: **NO**
- Staging accessed: **NO**
- Production/staging DSNs exposed: **NO**
- Production/staging configuration changed: **NO**
- Deployment performed: **NO**
- Database restore/export performed: **NO**
- Redis/RQ introduced: **NO**
