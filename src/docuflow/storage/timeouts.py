from __future__ import annotations

S3_RETRY_ATTEMPTS = 2


def storage_call_timeout_seconds(lease_minutes: int, *, attempts: int = S3_RETRY_ATTEMPTS) -> int:
    """Seconds allowed for one storage HTTP attempt.

    The deletion lease is renewed *before* the storage call. A hung S3 request
    with no timeout could outlive ``STORAGE_DELETE_LEASE_MINUTES`` and let
    another process reclaim the row. Bounding each attempt keeps the full
    retry budget under half the lease. Duplicate deletes are still possible if
    a provider ignores the timeout; finish updates remain owner-token
    conditional and object delete is idempotent.
    """
    lease_seconds = max(1, int(lease_minutes)) * 60
    budget = max(10, lease_seconds // 2)
    per_attempt = max(5, budget // max(1, attempts))
    return min(per_attempt, 60)
