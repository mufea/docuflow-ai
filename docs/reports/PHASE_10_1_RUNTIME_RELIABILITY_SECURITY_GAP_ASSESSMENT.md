# Phase 10.1 — Runtime reliability and security gap assessment

Assessment-only. No remediation was implemented. This report is **not**
production or staging certification.

Audit time: **10 Nov 2026, 20:56 Asia/Jakarta (WIB)**
(`2026-11-10T13:56:30Z`).

## 1. Executive summary

Phase 10.0A and 10.0B landed process-local auth rate limits, ignored
forwarding headers for client identity, cleaned documented temp-file
failure paths, and shut down the inline broker with `wait=True`. Those
behaviors are present on `origin/main`.

This audit confirms four remaining gaps and classifies them from source
and targeted local tests:

1. **Rate-limit memory:** `MemoryRateLimiter` pops expired timestamps
   but never deletes empty dictionary keys. Unbounded key growth is a
   **CONFIRMED** implementation property. Operational impact under
   current single-process Render traffic is a **POTENTIAL RISK**, not a
   demonstrated outage.
2. **Reverse proxy identity:** Application code does not trust
   `X-Forwarded-For` / `X-Real-IP` / `Forwarded`. Behind Render, many
   clients may share one TCP peer bucket. That is safer than header
   spoofing and is the intended 10.0B trade-off. Shared-bucket false
   positives in production remain **NOT VERIFIED**.
3. **SIGKILL / in-flight jobs:** `processing` rows are not reset on
   restart. Stale cleanup fails them after `JOB_STALE_MINUTES` (default
   90) and refunds reserved credits. Result documents can be committed
   before the job row is marked completed, so an interrupt during
   persist can leave orphaned files while the job later fails.
4. **Reset / verify tests:** Source applies per-client limits, but the
   only route-level HTTP `429` assertion in the suite is forgot-password.
   Reset-password and verify-email quota, isolation, and XFF bypass are
   **not** directly tested.

No P0 (immediate security or data-integrity) item is recommended.
Highest-severity **CONFIRMED** findings are **Medium**. Redis, RQ, and
trusted-proxy configuration are **not** required for the current
single-process `JOB_BROKER=inline` architecture.

## 2. Verified repository baseline

| Item | Value | Classification |
| --- | --- | --- |
| Audit time | 10 Nov 2026, 20:56 Asia/Jakarta | **VERIFIED** |
| Expected `origin/main` | `2c768e197bae43ad2bbe5f9b5b858d533a1b22fc` | **VERIFIED** (matches) |
| Actual `origin/main` | `2c768e197bae43ad2bbe5f9b5b858d533a1b22fc` | **VERIFIED** |
| Tip commit | Merge PR #52, 10 Nov 2026, 20:41 Asia/Jakarta | **VERIFIED** |
| Working tree at audit start | clean (docs branch; no uncommitted edits) | **VERIFIED** |
| Open PRs at audit | none | **VERIFIED** |
| Production / staging runtime | **NOT VERIFIED** this phase | — |

Source of truth for this report is `origin/main` at the SHA above.

## 3. Scope and methodology

Read-first inspection of rate limiting, client identity, inline job
lifecycle, and auth tests. Targeted local pytest only. Production
`DATABASE_URL` was **unset** for tests (`env -u DATABASE_URL`). The
value was not printed or used. No DSN, SQL, restore, deploy, or live
host mutation.

Inspected (not exhaustive of the whole repository):

- `src/docuflow/security/rate_limit.py`
- `src/docuflow/security/client_ip.py`
- `src/docuflow/api/routes/auth.py`
- `src/docuflow/services/auth.py`
- `src/docuflow/api/schemas.py`
- `src/docuflow/exceptions.py`
- `src/docuflow/main.py`
- `src/docuflow/api/deps.py`
- `src/docuflow/config.py`
- `src/docuflow/jobs/broker.py`
- `src/docuflow/jobs/runner.py`
- `src/docuflow/jobs/recovery.py`
- `src/docuflow/jobs/retention.py`
- `src/docuflow/jobs/refunds.py`
- `src/docuflow/jobs/scheduler.py`
- `src/docuflow/services/jobs.py`
- `src/docuflow/services/documents.py`
- `src/docuflow/models/entities.py`
- `src/docuflow/cleanup.py`
- `infra/render.yaml`
- `tests/test_phase10b_security.py`
- `tests/test_phase10_runtime_reliability.py`
- `tests/test_auth_api.py`
- `tests/test_phase96_safety.py`
- `tests/test_phase91_cleanup.py`
- `tests/conftest.py`
- Prior Phase 10.0 reports (historical, not re-certified)

## 4. Current architecture summary

Source-code and Blueprint facts. Production live behavior is **NOT
VERIFIED** here.

| Component | Evidence | Notes |
| --- | --- | --- |
| Auth rate limiter | `MemoryRateLimiter` in `AppContext` (`main.py` 78) | One in-process instance per API process |
| Client identity | `rate_limit_client_id` → `request.client.host` | No forwarding-header parse |
| Job broker | `JOB_BROKER=inline` in `infra/render.yaml` 66–69 | Thread pool, `WORKER_CONCURRENCY=2` |
| API process | `uvicorn docuflow.main:app --host 0.0.0.0 --port $PORT` | No `--workers`; no `numInstances` |
| Stale jobs | `JOB_STALE_MINUTES=90`; cleanup cron `*/15 * * * *` | API `CLEANUP_INTERVAL_SECONDS=0` |
| Credits | Reserve on create; settle on complete; refund on fail | Ledger key `refund:{job_id}` |

Owner-reported production hosts and `broker=inline` from Phase 9.11/9.12
are **not** re-probed. This audit does not claim they still match.

## 5. Rate limiter implementation and memory analysis

### 5.1 Current behavior

`MemoryRateLimiter.hit` (`src/docuflow/security/rate_limit.py` 10–24):

- Stores `dict[str, deque[float]]` via `defaultdict(deque)`.
- Uses `time.monotonic()` for the window.
- Holds a `threading.Lock` for the whole `hit` body.
- Pops timestamps older than `now - window_seconds`.
- Raises `RateLimitError` when `len(bucket) >= limit`.
- Otherwise appends `now`.

Auth routes (`auth.py`) call `hit` **before** `AuthService` work:

| Endpoint | Key | Limit / window |
| --- | --- | --- |
| `POST /v1/auth/register` | `register:{client}` | 5 / 60s |
| `POST /v1/auth/login` | `login:{client}` | 10 / 60s |
| `POST /v1/auth/forgot-password` | `forgot:{client}` | 8 / 60s |
| `POST /v1/auth/reset-password` | `reset:{client}` | 10 / 60s |
| `POST /v1/auth/verify-email` | `verify:{client}` | 10 / 60s |

Limits and windows are hardcoded at the call site, not settings.

Upload/job limiters (`upload:{user.id}`, `jobs:{user.id}`) are
authenticated and out of this phase’s primary scope.

### 5.2 Process-local properties

| Question | Answer | Classification |
| --- | --- | --- |
| Storage | In-process dict + deques | **CONFIRMED** |
| Shared across workers/replicas | No | **CONFIRMED** (no shared backend) |
| Restart | New `MemoryRateLimiter()` in `create_app` | **CONFIRMED**; counters reset |
| Intra-process concurrency | `threading.Lock` | **CONFIRMED** |
| Cross-process coordination | None | **CONFIRMED** |
| Clock | `time.monotonic()` | **CONFIRMED** |
| Configurable via env | No (hardcoded call-site ints) | **CONFIRMED** |

A lock does **not** coordinate replicas. Current Blueprint starts one
uvicorn process without `--workers`. Horizontal replicas are **NOT
APPLICABLE** to the inspected default stack; they would each have
independent counters if added later.

### 5.3 Memory growth

Expired **events** are removed (`while bucket and bucket[0] < cutoff:
popleft`). Empty **buckets** are not deleted. There is no:

- `del self._hits[key]`
- periodic sweep
- maximum key count
- TTL on the dictionary key

After a window expires, the key remains mapped to an empty `deque`.
Unique identifiers (especially `unknown` plus many peer hosts) therefore
accumulate keys for the life of the process.

Cleanup during normal `hit` is opportunistic and **per-key only**. There
is no global cleanup that would contend the lock across all keys.

This is **not** labeled a confirmed exploitable vulnerability: no
reproducer measured RSS growth. It is a **CONFIRMED** missing eviction
path and a **POTENTIAL RISK** under high identifier cardinality (for
example a scan of many unique source addresses, or IPv6). Auth-only
keyspace is five prefixes times client ids, not every HTTP route.

Existing tests (`test_memory_limiter_isolates_clients`) do not assert
key deletion.

### 5.4 Minimum remediation options (not implemented)

1. Delete the key when the deque is empty after expiry pops (**Small**).
2. Cap map size with oldest-key eviction (**Small/Medium**).
3. Shared store (Redis etc.) — **not** justified for the current
   single-process deploy (**P3**).

## 6. Reverse proxy and client identity analysis

### 6.1 How a client is identified

`rate_limit_client_id` (`client_ip.py` 6–17) returns
`request.client.host` or `"unknown"`. The docstring and implementation
do not read `X-Forwarded-For`, `X-Real-IP`, or `Forwarded`.

`main.py` has CORS, trusted-host, and security-header middleware. It
does **not** install `ProxyHeadersMiddleware`. `config.py` has
`DOCUFLOW_TRUSTED_HOSTS`, not a trusted-proxy list.

`test_rate_limit_client_id_ignores_forwarded_headers` asserts peer
`10.0.0.8` despite those three headers. `test_forgot_password_xff_cannot_bypass_peer_limit`
asserts nine forgot-password posts with rotating XFF/X-Real-IP still
hit the same 8/60s bucket.

### 6.2 Trust boundary

| Question | Answer | Classification |
| --- | --- | --- |
| App-layer forwarding headers ignored | Yes | **CONFIRMED** (source + tests) |
| Untrusted client spoof XFF to get a new bucket | No, at application layer | **CONFIRMED** for forgot-password route; reset/verify **NOT** route-tested |
| Runs behind reverse proxy | Render web service (Blueprint + historical 9.11 evidence) | Architecture **CONFIRMED**; live proxy hop **NOT VERIFIED** this phase |
| Many users share one peer | Likely when TLS terminates at Render | **POTENTIAL RISK** / design **CONFIRMED**; production false-positive rate **NOT VERIFIED** |
| Direct header spoof bypass | Blocked at app layer | **CONFIRMED** (forgot-password) |

Uvicorn 0.39 `Config`: `proxy_headers=True` by default;
`forwarded_allow_ips` defaults to `FORWARDED_ALLOW_IPS` or `127.0.0.1`.
The Render start command does not pass `--proxy-headers` or
`--forwarded-allow-ips`. `infra/render.yaml` does not set
`FORWARDED_ALLOW_IPS`. If that env were set to `*` in a dashboard, uvicorn
could rewrite `request.client` from forwarding headers **before**
`rate_limit_client_id` runs. Dashboard env is **NOT VERIFIED**. Treat
`FORWARDED_ALLOW_IPS=*` as an operational footgun, not a demonstrated
production state.

### 6.3 Option trade-offs (evaluation only)

| Option | Security | Ops complexity | Need now |
| --- | --- | --- | --- |
| 1. Current TCP peer | No header spoof; shared bucket false positives possible | None | **Current.** Fits single Render proxy + one API process |
| 2. Explicit trusted-proxy list | Can isolate clients if the proxy is trustworthy and hops are validated | Config, docs, misconfig risk | **Not required** until shared-bucket impact is measured |
| 3. Proxy identity after trusted-hop validation | Same as 2; fails open/closed depending on implementation | Higher | Same as 2 |
| 4. Shared rate-limit storage | Coordinates replicas only; does not fix identity | New dependency | **Not required.** Blueprint has one uvicorn process, no `--workers` |

Do not introduce Redis for rate limits on this architecture without a
measured replica or multi-worker requirement.

False negatives (under-limiting) happen if each replica or process has
its own map, or if the process restarts (Render free-tier sleep/spin).
False positives happen if many users share the proxy peer.

## 7. SIGKILL and inline job recovery analysis

### 7.1 Lifecycle (persisted vs in-memory)

| Step | Where | Durable? |
| --- | --- | --- |
| 1. Create | `JobService.create` → `status=queued`, credits reserved, commit | Yes |
| 2. Enqueue | `InlineBroker.enqueue` adds id to `_inflight`, `ThreadPoolExecutor.submit` | In-memory only |
| 3. Claim | `JobRunner.process` `UPDATE … WHERE status=queued` → `processing`, `heartbeat_at`, `attempt+1` | Yes |
| 4. Execute | Download, `_run_operation`, optional `store_result` | Partial: progress 25/80 committed; documents committed in `_store` |
| 5. Complete | `status=completed`, settle credits, commit | Yes |
| 6. Failure | `fail_job_and_refund` atomic status claim + ledger `refund:{job_id}` | Yes |
| 7. Graceful shutdown | `InlineBroker.shutdown(wait=True)` from lifespan | In-flight threads may finish a claim; SIGTERM path only |
| 8. SIGKILL | Process gone; `_inflight` lost | DB row stays `queued` or `processing` |
| 9. Stale detection | `cleanup_abandoned_jobs` / `_fail_stale_jobs` on heartbeat/started older than stale minutes | Yes |
| 10. Recovery | `recover_queued_jobs` re-enqueues up to 100 `queued` rows on API start. **Does not** touch `processing` | Yes for queued only |

`Job.attempt` is incremented on claim (`runner.py` 59) and is **not**
read for retry of `processing` rows.

Heartbeat is written at claim, after download (`progress=25`), and after
`_run_operation` (`progress=80`). There is **no** heartbeat during a
long PDF/AI operation.

### 7.2 SIGKILL outcomes

| When killed | Job row | Credits | Side effects |
| --- | --- | --- | --- |
| Before claim | `queued` | Reserved | Restart re-enqueues; claim is atomic so duplicate delivery does not double-run |
| During download / `_run_operation` | `processing` | Reserved until stale fail | Temp work dir is process-local; lost |
| During `store_result` | `processing`; **Document rows may already be committed** (`documents.py` `_store` commit at 350) | Reserved until stale fail/refund | Orphaned result objects/rows possible; job later `failed`/`timeout` |
| After settle, before commit | Uncommitted session lost | Reserved until stale fail | If `_store` already committed, same orphan risk |
| After completed commit | `completed` | Settled | Durable success |

`processing` jobs remain until stale cleanup. Default `JOB_STALE_MINUTES=90`.
Production API sets `CLEANUP_INTERVAL_SECONDS=0` (in-process scheduler
off). Blueprint cron is `*/15 * * * *` via `python -m docuflow.cleanup`.
Worst-case visibility of a stuck job is therefore about the stale
threshold plus one cron interval, **if** cron is running. Cron actually
running in production is **OWNER-REPORTED** historically (Phase 9.11)
and **NOT VERIFIED** this phase.

`shutdown(wait=True)` does not run on SIGKILL.

Duplicate processing of the same job id is prevented by the queued
claim (`rowcount != 1` skip). Tests:
`test_recovery_skips_processing_jobs_and_cleanup_fails_stale`,
`test_stale_job_cleanup_is_idempotent`,
`test_duplicate_recovery_does_not_double_charge`.

Stale fail does **not** retry the job. User may create a new job
(credits refunded). If result documents were already stored, a retry can
duplicate outputs. That is a **CONFIRMED** consistency gap from commit
ordering, not a demonstrated production incident.

Idempotency key on `Job` applies to **create**, not runner retry.

### 7.3 Recovery design options (not implemented)

| Option | Evidence missing/incomplete | Schema? | Need now |
| --- | --- | --- | --- |
| Keep existing stale cleanup | Works; delay up to ~90 min; no retry | No | **Keep.** Adequate for current inline hobby stack if cron runs |
| More frequent heartbeat during `_run_operation` | Long ops can look stale if they exceed 90 min without 80% heartbeat | No | **P2** unless jobs approach the stale window |
| Commit results with job completion (same transaction / outbox) | `_store` commits early | Possibly | **P1/P2** reliability; Medium complexity |
| Lease/heartbeat watchdog shorter than 90 min | Would fail live work if heartbeat gaps remain | Maybe | Not without heartbeat changes |
| Bounded retry of `processing` | No retry today; retry without idempotent `_store` duplicates files | Maybe `max_attempts` | **Defer** until persist is idempotent |
| Durable RQ/Redis worker | Not required for SIGKILL on single inline process | No | **P3**, separate approval |
| Process supervision | Render restarts the web process; graceful SIGTERM already waits | No | SIGKILL still bypasses wait |

Do not add Redis/RQ solely to “fix SIGKILL.” The durable state is
already PostgreSQL. The gap is interrupt during `processing` and early
document commits.

## 8. Reset-password and verify-email test coverage

### 8.1 Endpoint behavior (source)

Limiter runs first inside each route function, after FastAPI/Pydantic
validation of the body.

| Endpoint | Limit | Exceeded response | Sensitive work after hit | Invalid body |
| --- | --- | --- | --- | --- |
| login | 10/60s | `429` `rate_limited` “Too many requests. Try again shortly.” | Password check, session cookies | `422` before limiter |
| register | 5/60s | same | User insert, verify email token | `422` before limiter |
| forgot-password | 8/60s | same | `request_password_reset` (unknown email returns silently) | invalid email `422` |
| reset-password | 10/60s | same | `_consume_token` + password hash | short password `422` (`min_length=10`) |
| verify-email | 10/60s | same | `_consume_token` + `email_verified_at` | missing token `422` |

`RateLimitError` maps via `DocuflowError` handler (`main.py` 117–119) to
HTTP 429 JSON `{error, message}`. Message does not mention accounts.

Invalid **tokens** that pass schema still call `hit`, then
`AuthenticationError` (`401` “Invalid or expired token.”). Quota is
consumed. Not proven by a test.

Keys are independent (`reset:` vs `verify:` vs `login:` …). Source
**CONFIRMED**. Route-level independence is tested only for login vs
forgot (`test_login_limit_is_independent_of_forgot`).

### 8.2 Test gap matrix

| Check | login | register | forgot | reset | verify |
| --- | --- | --- | --- | --- | --- |
| Exceed configured limit → 429 | Missing | Missing | **Direct** (`test_forgot_password_quota_is_per_client`) | Missing | Missing |
| HTTP body `rate_limited` | Missing | Missing | Indirect (status only) | Missing | Missing |
| Per-client isolation | Missing | Missing | **Direct** | Missing | Missing |
| Independence vs other auth quotas | vs forgot only | Missing | vs login | Missing | Missing |
| XFF cannot bypass | Missing | Missing | **Direct** | Missing | Missing |
| Invalid token still rate-limited | n/a | n/a | n/a | Missing | Missing |
| Valid token path under limit | Functional login tests, not quota | Functional register | Known/unknown 200 | **No route tests found** | **No route tests found** |

`rg` over `tests/` for `reset-password`, `verify-email`,
`reset_password`, `verify_email` as route calls: only forgot-password
paths and `test_register_succeeds_when_verify_email_fails` (email
backend failure on **register**, not `POST /v1/auth/verify-email`).

The only `status_code == 429` assertion in `tests/` is forgot-password.

Phase 10.0B documented reset/verify limits as “unit-covered by the same
`hit` helper pattern.” That is **indirect** coverage of `MemoryRateLimiter`,
not endpoint tests. This audit treats that as a **CONFIRMED** test gap.

### 8.3 Safe local validation executed

See section 13. No tests were added or modified.

## 9. Evidence register

Approval is required before implementing any remediation below.

### F-A1 — Process-local rate-limit state

- **Classification:** CONFIRMED
- **Severity:** Informational
- **Where:** `rate_limit.py` 10–24; `main.py` 78
- **Evidence:** In-process dict; one limiter per `create_app`.
- **Impact:** Replicas/restarts do not share counts.
- **Remediation:** None required for current Blueprint. Do not add Redis by default.
- **Approval:** Yes if anyone proposes shared storage.

### F-A2 — Empty buckets retained (unbounded keys)

- **Classification:** CONFIRMED (no key delete); POTENTIAL RISK (memory impact)
- **Severity:** Low
- **Where:** `rate_limit.py` 15–24
- **Evidence:** `popleft` only; no `del self._hits[key]`; no max size.
- **Reproduction:** No RSS test run (by design).
- **Impact:** Slow growth with unique client ids for process lifetime.
- **Remediation:** Delete empty deques after expiry pops. **Small.**
- **Approval:** Yes.

### F-A3 — Restart clears limits

- **Classification:** CONFIRMED
- **Severity:** Low
- **Where:** `main.py` 72–79
- **Impact:** Render restart/sleep resets auth throttles.
- **Remediation:** Accept for single process, or document. Shared store is P3.
- **Approval:** Yes for any shared-store change.

### F-A4 — Intra-process lock; no load proof

- **Classification:** CONFIRMED (lock present); concurrent correctness under load NOT VERIFIED
- **Severity:** Informational
- **Where:** `rate_limit.py` 13, 17
- **Remediation:** None. Do not add a global sweep that holds the lock over all keys.
- **Approval:** n/a for no-op.

### F-B1 — Forwarding headers ignored at app layer

- **Classification:** CONFIRMED
- **Severity:** Informational (safeguard)
- **Where:** `client_ip.py` 6–17; tests in `test_phase10b_security.py` 28–38, 87–99
- **Remediation:** Keep. Do not parse XFF without a trusted-proxy design.
- **Approval:** Yes for any header-trust change.

### F-B2 — Shared TCP peer behind reverse proxy

- **Classification:** CONFIRMED (design); production false-positive rate NOT VERIFIED
- **Severity:** Medium
- **Where:** `client_ip.py` 8–12; Render reverse proxy architecture
- **Impact:** Login/forgot/reset/verify quotas may apply to all users behind one proxy IP.
- **Remediation:** Measure first. Trusted-proxy parsing is P3 until then.
- **Approval:** Yes.

### F-B3 — Uvicorn `proxy_headers` default

- **Classification:** CONFIRMED (library default); production `FORWARDED_ALLOW_IPS` NOT VERIFIED
- **Severity:** Low
- **Where:** uvicorn 0.39 `Config`; `infra/render.yaml` startCommand
- **Impact:** If `FORWARDED_ALLOW_IPS=*` were set, peer identity could become header-derived.
- **Remediation:** Document that this env must not be `*`. Optionally pass
  `--forwarded-allow-ips 127.0.0.1` explicitly. **Small**, ops/docs.
- **Approval:** Yes before start-command changes.

### F-C1 — SIGKILL leaves `processing` until stale cleanup

- **Classification:** CONFIRMED
- **Severity:** Medium
- **Where:** `recovery.py` 25–29, 36–38; `retention.py` 139–186; `broker.py` 46–48
- **Tests:** `test_recovery_skips_processing_jobs_and_cleanup_fails_stale` **PASS**
- **Impact:** Jobs can look stuck for up to `JOB_STALE_MINUTES` (90) plus cron lag; then fail + refund.
- **Remediation:** Keep cleanup. Do not reset `processing` on startup (would race a live thread). Optional: surface “timed out” UX. Heartbeat during long ops is P2.
- **Approval:** Yes for behavior changes.

### F-C2 — Result documents committed before job completion

- **Classification:** CONFIRMED
- **Severity:** Medium
- **Where:** `documents.py` `_store` 349–350; `runner.py` 139–150 vs 75–82
- **Evidence:** `session.commit()` in `_store` precedes `job.status = "completed"`.
- **Reproduction:** Structural; SIGKILL not executed in this audit.
- **Impact:** Orphaned result files/rows; job later failed and refunded; user retry can duplicate outputs. Credits are not double-settled (`fail_job_and_refund` + ledger idempotency).
- **Remediation:** Persist results in the same transaction as completion, or an outbox tied to job id. **Medium.** Retry of `processing` must wait for this.
- **Approval:** Yes.

### F-C3 — No processing-job retry; `attempt` unused for retry

- **Classification:** CONFIRMED
- **Severity:** Informational
- **Where:** `runner.py` 59; no other `Job.attempt` readers in `src/`
- **Impact:** Interrupted work is failed, not retried. Safer than duplicate side effects.
- **Remediation:** Defer retry until F-C2 is addressed.
- **Approval:** Yes.

### F-C4 — Heartbeat gap during `_run_operation`

- **Classification:** CONFIRMED (no heartbeat in `_run_operation`); live timeout of a running job POTENTIAL RISK
- **Severity:** Low
- **Where:** `runner.py` 130–136 vs 152–266
- **Impact:** A single operation longer than `effective_stale_minutes` (floor ≥ worker timeout, typically 90) could be failed while still running.
- **Remediation:** Periodic heartbeat inside long operations, or keep 90 min if jobs are shorter. **Small/Medium.**
- **Approval:** Yes.

### F-D1 — Reset/verify limiters present, route tests missing

- **Classification:** CONFIRMED
- **Severity:** Medium (coverage), not a demonstrated limiter bypass
- **Where:** `auth.py` 164–189; `tests/test_phase10b_security.py`; no reset/verify route tests
- **Evidence:** Only forgot-password has HTTP 429 assertions. `MemoryRateLimiter.hit` is unit-tested with `forgot:` keys.
- **Impact:** Regressions on reset/verify quotas, isolation, or XFF would not be caught.
- **Remediation:** Add route tests mirroring forgot-password for reset and verify (and login/register exceed-quota). **Small.** Local sqlite `TestClient` only.
- **Approval:** Yes.

### F-D2 — Invalid reset/verify tokens consume quota

- **Classification:** CONFIRMED (source order); test coverage NOT VERIFIED
- **Severity:** Low
- **Where:** `auth.py` 171–174, 185–188; `auth.py` service `_consume_token`
- **Impact:** Token guessing is bounded per peer (and per process). Shared proxy tightens that bound (F-B2).
- **Remediation:** Keep consuming quota on invalid tokens. Add a test. Do not skip `hit` on 401.
- **Approval:** Yes for test-only change.

## 10. Prioritized remediation matrix

No P0 item. Nothing here is a demonstrated remote bypass or credit
double-spend.

| ID | Priority | Findings | Likely files | Schema | Deps | Render | Extra services | Complexity | Tests | Staging later |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | **P2** (do first: small, high value) | F-D1, F-D2 | `tests/test_phase10b_security.py` | No | No | No | No | Small | Reset/verify/login/register 429, isolation, independence, XFF; invalid token still 429 then 401 | Optional; local suite is the gate |
| R2 | **P2** | F-A2 | `rate_limit.py` + unit test | No | No | No | No | Small | Empty key removed after window; cardinality bound if cap added | Not required |
| R3 | **P2** | F-B3 | Docs and/or startCommand | No | No | Maybe start args | No | Small | None (config). Do not set `FORWARDED_ALLOW_IPS=*` | Confirm start command on staging |
| R4 | **P1** if product wants no orphan results; else P2 | F-C2 | `documents.py`, `runner.py`, possibly models | Maybe | No | No | No | Medium | Kill/interrupt after `_store` before complete; no orphan or job points at results; refund still idempotent | Staging job interrupt **if** owner approves a non-prod drill |
| R5 | **P2** | F-C4 | `runner.py` | No | No | No | No | Small/Medium | Heartbeat updates during a delayed operation; stale cleanup leaves live heartbeats | Not required |
| R6 | **P3** | F-A1, F-B2 | New settings, possibly Redis | No | Maybe | Maybe | Only if replicas exist | Large | Cross-process shared counts | Only after architecture change |
| R7 | **P3** | F-C1 | RQ worker | No | Redis + worker | Yes | Yes | Large | Separate scaling phase | Separate approval |

Trade-offs: R1/R2 do not change production behavior except R2’s memory
map. R4 changes crash semantics and needs careful credit tests. R6/R7
are architectural and are **not** the minimum fix.

## 11. Minimum recommended next implementation phase

**Proposed Phase 10.2 (implementation, after owner approval):**

1. Route-level rate-limit tests for reset-password and verify-email
   (R1). Include login/register exceed-quota while touching that file.
2. Delete empty limiter keys (R2).
3. Document uvicorn `FORWARDED_ALLOW_IPS` (R3) without enabling header
   trust.

Defer R4/R5 unless the owner prioritizes interrupt-consistent job
results. Defer Redis/RQ.

Do **not** start that phase in this PR.

## 12. Risks and unresolved questions

- Production `FORWARDED_ALLOW_IPS` dashboard value: **NOT VERIFIED**.
- Whether Render’s hop is trusted by uvicorn’s default `127.0.0.1` allow
  list: **NOT VERIFIED** (likely not; then `request.client` is the proxy).
- Cleanup cron currently running: **NOT VERIFIED** this phase
  (Blueprint says `*/15`; Phase 9.11 owner said it was running).
- RSS growth of `MemoryRateLimiter` under many unique IDs: **NOT VERIFIED**.
- Actual shared-bucket user impact on `docuflowai.site`: **NOT VERIFIED**.
- SIGKILL during `store_result` orphan documents: structurally
  **CONFIRMED**, not reproduced with a live kill in this audit.
- Phase 9.12 production functional verification does **not** cover
  10.0A/B or these gaps.

## 13. Tests executed and results

All with `env -u DATABASE_URL` (production URL was set in the shell
environment; it was unset for pytest and never printed).

Fixtures: sqlite via `tests/conftest.py`, `JOB_BROKER=inline`,
`STORAGE_BACKEND=filesystem`, `AI_PROVIDER=mock`,
`cleanup_interval_seconds=0`. No real email, no external storage.

| Command | Result |
| --- | --- |
| `uv run pytest -q tests/test_phase10b_security.py tests/test_phase10_runtime_reliability.py tests/test_phase96_safety.py::test_recovery_skips_processing_jobs_and_cleanup_fails_stale tests/test_phase91_cleanup.py::test_stale_job_cleanup_is_idempotent` | **15 passed** in 1.77s |

Skipped / not run:

| Item | Reason |
| --- | --- |
| Full unit suite | Documentation/assessment phase; not required |
| Integration (`-m integration`) | Needs `TEST_DATABASE_URL`; not required for these findings |
| Web lint/tests | No web change |
| Production/staging smoke | Prohibited |
| Load / RSS benchmark | Prohibited |
| SIGKILL of a live worker | Would be a process experiment; not required given source + existing stale tests |

Markdown lint: **not available** in this repository.

## 14. No application changes

This phase added only this report. No Python, TypeScript, tests,
dependencies, migrations, Render Blueprint, or configuration files were
modified.

## 15. Production and staging safety declaration

- No production or staging access, shell, or HTTP mutation.
- No DSN printed or copied.
- No SQL, restore, PITR, export, backup, or R2/object mutation.
- No Redis/worker/proxy provisioning.
- No deploy.
- Tests used isolated sqlite and `env -u DATABASE_URL`.

Phase 10.0 production verification remains **NOT VERIFIED**.
Phase 10.0 staging verification remains **NOT VERIFIED**.
Phase 9.15 remains **OPEN**. Backup assurance remains **INCOMPLETE**.
Production DR readiness remains **NOT DEMONSTRATED**.
