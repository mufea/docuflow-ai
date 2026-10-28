from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.db import Base
from docuflow.exceptions import InsufficientCreditsError
from docuflow.models import Plan, User
from docuflow.security.passwords import hash_password


def _session(tmp_path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'credits.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    session.add(
        Plan(
            slug="free",
            name="Free",
            monthly_credits=20,
            max_file_bytes=1_000_000,
            max_pages=10,
            max_ai_requests_per_day=2,
            features={},
        )
    )
    user = User(email="ledger@example.com", password_hash=hash_password("super-secret-1"), name="Ledger")
    session.add(user)
    session.commit()
    return session


def test_reserve_settle_and_refund(tmp_path) -> None:
    session = _session(tmp_path)
    user = session.query(User).one()
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 5, job_id="job-a")
    account = service.ensure_account(user)
    assert account.reserved == 5
    assert account.balance == 20
    service.settle(user, 5, job_id="job-a")
    account = service.ensure_account(user)
    assert account.reserved == 0
    assert account.balance == 15
    service.reserve(user, 4, job_id="job-b")
    service.refund_reservation(user, 4, job_id="job-b")
    account = service.ensure_account(user)
    assert account.reserved == 0
    assert account.balance == 15
    service.reserve(user, 4, job_id="job-b")
    service.refund_reservation(user, 4, job_id="job-b")
    assert account.balance == 15


def test_idempotent_duplicate_reserve(tmp_path) -> None:
    session = _session(tmp_path)
    user = session.query(User).one()
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 3, job_id="same")
    service.reserve(user, 3, job_id="same")
    account = service.ensure_account(user)
    assert account.reserved == 3


def test_insufficient_credits(tmp_path) -> None:
    session = _session(tmp_path)
    user = session.query(User).one()
    service = CreditService(session)
    service.ensure_account(user)
    try:
        service.reserve(user, 500, job_id="too-big")
        raise AssertionError("expected insufficient credits")
    except InsufficientCreditsError:
        pass


def test_ledger_matches_balance_changes(tmp_path) -> None:
    session = _session(tmp_path)
    user = session.query(User).one()
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 2, job_id="job-c")
    service.settle(user, 2, job_id="job-c")
    from docuflow.models import CreditLedger

    entries = session.query(CreditLedger).all()
    balance_entries = [item for item in entries if item.entry_type in {"grant", "settle"}]
    assert sum(item.amount for item in balance_entries) == service.ensure_account(user).balance
    assert all(isinstance(item.amount, int) for item in entries)
