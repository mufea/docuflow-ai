# Phase 9.12 — Production functional verification and security validation

Owner-run Gates 1–3 against production. This agent did **not** receive
passwords, cookies, document ids, or signed URLs. Application code was
not changed for this evidence.

Evidence timestamp: **7 Nov 2026, 20:33 Asia/Jakarta (WIB)**.
Script: `scripts/production_smoke.py` (host-locked to `docuflowai.site`).
Authorization: owner, 18:53 Asia/Jakarta (Gates 1–3, dedicated test
accounts, synthetic PDF, delete only those test documents).

`origin/main` at this report: `ea0fb07` (PR #23 merge).

## Executive summary

Production is **deployed** and **health-verified** (Phase 9.11 + 9.12A
Gate 0). Owner-run smoke now also **functionally** and **isolation-**
verified for the six mandatory workflows.

This is **not** a pentest, load test, restore drill, or hosted Alembic
inspect. Mock AI and console email remain as accepted.

| Classification | Status |
| --- | --- |
| DEPLOYED | **YES** |
| HEALTH VERIFIED | **YES** |
| FUNCTIONALLY VERIFIED | **YES** |
| SECURITY VERIFIED | **YES** (required authz/isolation; not a full audit) |
| PRODUCTION VERIFIED | **YES** (Phase 9.12 mandatory acceptance) |

Outstanding residual risks: Free-web spin-down vs inline jobs; mock AI /
console email; no live 50 MiB upload; no signed-URL expiry wait; no
production Alembic inspect; no backup restore drill; in-process rate
limiter untested on production.

## Verification matrix

| Test | Result | Evidence |
| --- | --- | --- |
| Authentication | **PASS** | `A_invalid_login 401`; `A_login 200`; `A_me 200`; `B_login 200`; `B_me 200`; `A_logout 200`; `A_me_after_logout 401`; `A_login2 200` |
| Upload | **PASS** | `A_upload 200`; `A_upload_id SET`; `A_upload_spoof 415` |
| Extraction | **PASS** | `A_extract_create 200`; `A_extract_http 200`; `A_extract_status completed`; `A_extract_text present` (`extract_text`, inline) |
| Download | **PASS** | `A_download 302` (redirect not followed; Location not printed) |
| Delete | **PASS** | `A_DELETE 200`; `A_GET_after 404` |
| Cross-user isolation | **PASS** | `B_list 200`; `B_list_has_A_doc no`; `B_GET 403`; `B_download 403`; `B_DELETE 403`; `unauth_GET 401` |

No FAIL, BLOCKED, or SKIPPED rows in the six mandatory areas.

## Sanitized owner output

```
A_invalid_login 401
A_login 200
A_me 200
B_login 200
B_me 200
A_logout 200
A_me_after_logout 401
A_login2 200
A_upload 200
A_upload_id SET
A_upload_spoof 415
A_extract_create 200
A_extract_http 200
A_extract_status completed
A_extract_text present
A_download 302
B_list 200
B_list_has_A_doc no
B_GET 403
B_download 403
B_DELETE 403
unauth_GET 401
A_DELETE 200
A_GET_after 404
```

## Infrastructure verification

| Item | Result | Source |
| --- | --- | --- |
| API `/health` | PASS 200 `docuflow-api` | Independent Gate 0 (9.12A, 18:39) |
| API `/ready` | PASS `broker=inline` `rq_workers=0` db/storage true | Independent Gate 0 |
| Web CMS | PASS 200 | Independent Gate 0 |
| Database | Ready check true; live extract/upload imply DB writes | Independent + owner smoke |
| Storage | Ready check true; upload 200 + download 302 | Independent + owner smoke |
| Inline broker | `/ready` + extract `completed` | Independent + owner smoke |
| Redis / worker | Owner-reported **absent** | Phase 9.11 (not re-inspected) |
| Cleanup cron | Owner-reported **running** | Phase 9.11 (not independently timed) |
| Postgres plan / backups | Owner-reported Basic + backups | Phase 9.11 |

## Security findings

Live production checks used two dedicated test accounts and one synthetic
PDF. No aggressive scanner, fuzzing, or pentest.

| Sev | Description | Component | Evidence | Impact | Remediation | Code change |
| --- | --- | --- | --- | --- | --- | --- |
| — | Authn enforced | `/v1/auth/*`, documents | invalid 401; unauth GET 401; logout then `/me` 401 | — | none | no |
| — | IDOR / ownership | documents + jobs | B GET/download/DELETE 403; list lacks A's id | — | none | no |
| — | MIME sniff | upload | spoofed `.pdf` text → 415 | — | none | no |
| Info | Existence oracle: other-user id → 403, missing → 404 | `DocumentService.get_owned` | B_GET 403 vs A_GET_after 404 | Reveals that an id exists, not contents | Optional unify 404; low | no (not blocking) |
| Info | Signed URL TTL not waited out | S3 302, default 600s | Download 302 only; Location not captured | Expiry unproven live | Optional later | no |
| Info | 50 MiB size limit not sent | `MAX_UPLOAD_BYTES` | SKIPPED by design | Limit unproven live | Optional later | no |
| Info | In-process rate limiter | `MemoryRateLimiter` | NOT TESTED | Resets on spin-down | Accept for Free web | no |
| Info | Mock AI / console email | providers | unchanged | No live model/SMTP | Owner decision | no |

No Critical or High findings from this phase.

Direct object-key bypass was not attempted (keys are not in `DocumentOut`;
B received 403, not file bytes).

## Production verification conclusion

Phase 9.12 mandatory acceptance **passed**:

1. DEPLOYED — **YES**
2. HEALTH VERIFIED — **YES**
3. FUNCTIONALLY VERIFIED — **YES**
4. SECURITY VERIFIED — **YES** (required isolation/authz)
5. PRODUCTION VERIFIED — **YES**

Not in scope / still residual: hosted Alembic on `docuflow-db`, backup
restore drill, paid always-on API, live AI, real email, full pentest.

## Safety

- Production mutations: owner-run only; test document deleted (`A_DELETE 200`)
- Credentials: not pasted
- Application code this report: **NO**
