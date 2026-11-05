from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from docuflow.billing.plans import PricingPolicy
from docuflow.exceptions import ConflictError, InsufficientCreditsError
from docuflow.models import CreditAccount, CreditLedger, Plan, User


@dataclass(frozen=True, slots=True)
class RefundResult:
    released: int = 0
    already_refunded: bool = False
    missing_reservation: bool = False
    skipped: bool = False
    settled: bool = False


class CreditService:
    def __init__(self, session: Session, *, policy: PricingPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or PricingPolicy()

    def ensure_account(self, user: User) -> CreditAccount:
        account = self.session.get(CreditAccount, user.id)
        if account:
            self._lock(account)
            self._maybe_reset_period(account)
            return account
        plan = self.session.get(Plan, user.plan_slug)
        allowance = plan.monthly_credits if plan else 0
        account = CreditAccount(
            user_id=user.id,
            balance=allowance,
            reserved=0,
            period_allowance=allowance,
            period_used=0,
            period_start=datetime.now(UTC),
        )
        self.session.add(account)
        self.session.flush()
        self._write(
            user_id=user.id,
            amount=allowance,
            entry_type="grant",
            description=f"Monthly allowance for {user.plan_slug}",
            idempotency_key=f"grant:{user.id}:{account.period_start.date().isoformat()}",
        )
        return account

    def reserve(self, user: User, amount: int, *, job_id: str) -> None:
        if amount < 0:
            raise ConflictError("Cannot reserve a negative credit amount.")
        account = self.ensure_account(user)
        self._lock(account)
        available = account.balance - account.reserved
        if amount > available and not self.policy.allow_negative:
            raise InsufficientCreditsError(
                "Not enough credits for this operation.",
                details={"required": amount, "available": max(available, 0)},
            )
        if amount == 0:
            return
        key = f"reserve:{job_id}"
        if self.session.scalar(select(CreditLedger).where(CreditLedger.idempotency_key == key)):
            return
        account.reserved += amount
        account.version += 1
        self._write(
            user_id=user.id,
            amount=0,
            entry_type="reserve",
            job_id=job_id,
            description=f"Reserved {amount} credits",
            idempotency_key=key,
        )

    def settle(self, user: User, amount: int, *, job_id: str) -> None:
        account = self.ensure_account(user)
        self._lock(account)
        if self.session.scalar(select(CreditLedger).where(CreditLedger.idempotency_key == f"settle:{job_id}")):
            return
        reserved = min(account.reserved, amount)
        account.reserved -= reserved
        account.balance -= amount
        account.period_used += amount
        account.version += 1
        if account.balance < 0 and not self.policy.allow_negative:
            raise InsufficientCreditsError("Credit settlement would make the balance negative.")
        self._write(
            user_id=user.id,
            amount=-amount,
            entry_type="settle",
            job_id=job_id,
            description="Settled job charge",
            idempotency_key=f"settle:{job_id}",
        )
        if reserved:
            self._write(
                user_id=user.id,
                amount=0,
                entry_type="release_reserve",
                job_id=job_id,
                description="Release reservation at settlement",
                idempotency_key=f"release-settle:{job_id}",
            )

    def refund_reservation(self, user: User, amount: int, *, job_id: str) -> RefundResult:
        """Release a job reservation without changing the available balance.

        Idempotent on ``refund:{job_id}``. A concurrent duplicate hits the
        unique ledger constraint and is treated as already refunded. A settled
        job is never refunded. Missing or partial reserved balances release
        only what is still reserved and never drive ``reserved`` negative.
        """
        if not self.policy.refund_failed_jobs or amount <= 0:
            return RefundResult(skipped=True)
        account = self.ensure_account(user)
        self._lock(account)
        if self._ledger_exists(f"settle:{job_id}"):
            return RefundResult(skipped=True, settled=True)
        if self._ledger_exists(f"refund:{job_id}"):
            return RefundResult(already_refunded=True)
        available_reserved = max(account.reserved, 0)
        release = min(available_reserved, amount)
        missing = available_reserved <= 0
        try:
            with self.session.begin_nested():
                if self._ledger_exists(f"refund:{job_id}"):
                    return RefundResult(already_refunded=True)
                if release > 0:
                    account.reserved -= release
                    account.version += 1
                self._write(
                    user_id=user.id,
                    amount=0,
                    entry_type="refund_reserve",
                    job_id=job_id,
                    description="Refund reservation for failed or cancelled job",
                    idempotency_key=f"refund:{job_id}",
                )
        except IntegrityError:
            self.session.refresh(account)
            return RefundResult(already_refunded=True)
        return RefundResult(released=release, missing_reservation=missing)

    def grant(
        self, user: User, amount: int, *, reason: str, idempotency_key: str, payment_id: str | None = None
    ) -> None:
        if amount <= 0:
            raise ConflictError("Grant amount must be positive.")
        account = self.ensure_account(user)
        self._lock(account)
        if self._ledger_exists(idempotency_key):
            return
        account.balance += amount
        account.version += 1
        self._write(
            user_id=user.id,
            amount=amount,
            entry_type="grant",
            payment_id=payment_id,
            description=reason,
            idempotency_key=idempotency_key,
        )

    def available(self, user: User) -> int:
        account = self.ensure_account(user)
        return account.balance - account.reserved

    def _lock(self, account: CreditAccount) -> None:
        self.session.execute(select(CreditAccount).where(CreditAccount.user_id == account.user_id).with_for_update())
        self.session.refresh(account)

    def _maybe_reset_period(self, account: CreditAccount) -> None:
        now = datetime.now(UTC)
        start = account.period_start
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if now.year == start.year and now.month == start.month:
            return
        user = self.session.get(User, account.user_id)
        plan = self.session.get(Plan, user.plan_slug) if user else None
        allowance = plan.monthly_credits if plan else account.period_allowance
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        key = f"grant:{account.user_id}:{period_start.date().isoformat()}"
        account.period_start = period_start
        account.period_allowance = allowance
        account.period_used = 0
        if self._ledger_exists(key):
            return
        account.balance += allowance
        self._write(
            user_id=account.user_id,
            amount=allowance,
            entry_type="grant",
            description="Monthly credit refresh",
            idempotency_key=key,
        )

    def _ledger_exists(self, idempotency_key: str) -> bool:
        row = self.session.scalar(select(CreditLedger).where(CreditLedger.idempotency_key == idempotency_key))
        return row is not None

    def _write(
        self,
        *,
        user_id: str,
        amount: int,
        entry_type: str,
        description: str,
        idempotency_key: str,
        job_id: str | None = None,
        payment_id: str | None = None,
    ) -> None:
        existing = self.session.scalar(select(CreditLedger).where(CreditLedger.idempotency_key == idempotency_key))
        if existing:
            return
        self.session.add(
            CreditLedger(
                user_id=user_id,
                amount=amount,
                entry_type=entry_type,
                job_id=job_id,
                payment_id=payment_id,
                description=description,
                idempotency_key=idempotency_key,
            )
        )
        self.session.flush()
