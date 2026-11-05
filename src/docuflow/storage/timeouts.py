from __future__ import annotations

from dataclasses import dataclass

# Total HTTP tries for one SDK call, including the initial request.
# Botocore Config "max_attempts" means extra *retries* (initial + N), which
# accidentally added one more try than Phase 9.3 budgeted. Prefer
# "total_max_attempts" (botocore 1.43+).
S3_TOTAL_MAX_ATTEMPTS = 2
S3_RETRY_ATTEMPTS = S3_TOTAL_MAX_ATTEMPTS  # historical alias used in Phase 9.3 tests

# Documented cap from botocore.retries.standard.ExponentialBackoff._MAX_BACKOFF.
# Jitter and x-amz-retry-after can still exceed this; it is not an SDK hard wall.
S3_STANDARD_MAX_BACKOFF_SECONDS = 20
S3_CONNECT_TIMEOUT_CAP = 10
S3_MIN_READ_TIMEOUT = 5
S3_MAX_READ_TIMEOUT = 60
S3_MIN_LEASE_MINUTES = 1


def _as_positive_int(value: object, *, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


@dataclass(frozen=True, slots=True)
class StorageCallBudget:
    """Designed timeout budget for one S3 SDK call.

    ``http_budget_seconds`` is ``attempts * (connect + read)`` and is kept at
    or below half the deletion lease. ``designed_ceiling_seconds`` adds the
    documented standard-mode backoff cap. Botocore does not expose a hard
    wall-clock deadline (DNS, jitter, Retry-After, and providers that ignore
    client timeouts can overrun). Application-level ``storage_deletions``
    retries are a separate, bounded outbox loop and are not multiplied into
    this SDK call.
    """

    lease_seconds: int
    total_max_attempts: int
    retry_attempts: int
    connect_timeout_seconds: int
    read_timeout_seconds: int
    http_budget_seconds: int
    designed_ceiling_seconds: int
    standard_max_backoff_seconds: int

    @property
    def botocore_retries(self) -> dict[str, int | str]:
        return {"total_max_attempts": self.total_max_attempts, "mode": "standard"}


def storage_call_budget(
    lease_minutes: object,
    *,
    attempts: object = S3_TOTAL_MAX_ATTEMPTS,
) -> StorageCallBudget:
    lease_minutes_i = _as_positive_int(lease_minutes, default=S3_MIN_LEASE_MINUTES, minimum=S3_MIN_LEASE_MINUTES)
    total_attempts = _as_positive_int(
        attempts,
        default=S3_TOTAL_MAX_ATTEMPTS,
        minimum=1,
        maximum=S3_TOTAL_MAX_ATTEMPTS,
    )
    lease_seconds = lease_minutes_i * 60
    half_lease = max(10, lease_seconds // 2)
    per_attempt = half_lease / total_attempts
    if per_attempt > S3_CONNECT_TIMEOUT_CAP + S3_MIN_READ_TIMEOUT:
        connect = S3_CONNECT_TIMEOUT_CAP
        read = int(per_attempt - connect)
    else:
        read = max(S3_MIN_READ_TIMEOUT, int(per_attempt // 2))
        connect = min(S3_CONNECT_TIMEOUT_CAP, read)
    read = min(S3_MAX_READ_TIMEOUT, max(S3_MIN_READ_TIMEOUT, read))
    connect = min(S3_CONNECT_TIMEOUT_CAP, max(1, connect), read)
    retries = total_attempts - 1
    http_budget = total_attempts * (connect + read)
    designed = http_budget + retries * S3_STANDARD_MAX_BACKOFF_SECONDS
    return StorageCallBudget(
        lease_seconds=lease_seconds,
        total_max_attempts=total_attempts,
        retry_attempts=retries,
        connect_timeout_seconds=connect,
        read_timeout_seconds=read,
        http_budget_seconds=http_budget,
        designed_ceiling_seconds=designed,
        standard_max_backoff_seconds=S3_STANDARD_MAX_BACKOFF_SECONDS,
    )


def storage_call_timeout_seconds(
    lease_minutes: object,
    *,
    attempts: object = S3_TOTAL_MAX_ATTEMPTS,
) -> int:
    """Read timeout for one storage HTTP attempt (see ``storage_call_budget``)."""
    return storage_call_budget(lease_minutes, attempts=attempts).read_timeout_seconds
