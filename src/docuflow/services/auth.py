from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.email.backend import EmailBackend
from docuflow.exceptions import AuthenticationError, ConflictError, ValidationError
from docuflow.models import EmailToken, SessionToken, User
from docuflow.security.passwords import hash_password, verify_password
from docuflow.security.tokens import digest_equals, hash_token, random_token

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(self, session: Session, settings: Settings, email: EmailBackend) -> None:
        self.session = session
        self.settings = settings
        self.email = email

    def register(self, *, email: str, password: str, name: str) -> User:
        normalized = email.strip().lower()
        if not EMAIL_RE.match(normalized):
            raise ValidationError("Enter a valid email address.")
        if len(password) < 10:
            raise ValidationError("Password must be at least 10 characters.")
        if len(name.strip()) < 2:
            raise ValidationError("Name is required.")
        existing = self.session.scalar(select(User).where(User.email == normalized))
        if existing:
            raise ConflictError("An account with this email already exists.")
        user = User(
            email=normalized,
            password_hash=hash_password(password),
            name=name.strip()[:120],
            plan_slug=self.settings.default_plan,
        )
        self.session.add(user)
        self.session.flush()
        CreditService(self.session).ensure_account(user)
        self.session.commit()
        self._issue_email_token(user, "verify")
        return user

    def login(self, *, email: str, password: str, user_agent: str | None) -> tuple[User, str, str]:
        user = self.session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or user.deleted_at is not None or not user.is_active:
            raise AuthenticationError("Invalid email or password.")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        raw = random_token()
        csrf = random_token(16)
        session = SessionToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            csrf_token=csrf,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.session_ttl_seconds),
            user_agent=(user_agent or "")[:300],
        )
        self.session.add(session)
        self.session.commit()
        return user, raw, csrf

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        token = self.session.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))
        if token and token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)
            self.session.commit()

    def user_from_session(self, raw_token: str | None) -> tuple[User, SessionToken] | None:
        if not raw_token:
            return None
        token = self.session.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))
        if token is None or token.revoked_at is not None:
            return None
        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            return None
        user = self.session.get(User, token.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            return None
        return user, token

    def request_password_reset(self, email: str) -> None:
        user = self.session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return
        self._issue_email_token(user, "reset")

    def reset_password(self, token: str, new_password: str) -> None:
        if len(new_password) < 10:
            raise ValidationError("Password must be at least 10 characters.")
        record = self._consume_token(token, "reset")
        user = self.session.get(User, record.user_id)
        if user is None:
            raise AuthenticationError("Invalid or expired token.")
        user.password_hash = hash_password(new_password)
        self.session.commit()

    def verify_email(self, token: str) -> None:
        record = self._consume_token(token, "verify")
        user = self.session.get(User, record.user_id)
        if user:
            user.email_verified_at = datetime.now(UTC)
            self.session.commit()

    def delete_account(self, user: User) -> None:
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        user.email = f"deleted-{user.id}@invalid.local"
        tokens = self.session.scalars(select(SessionToken).where(SessionToken.user_id == user.id))
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
        self.session.commit()

    def _issue_email_token(self, user: User, purpose: str) -> None:
        raw = random_token()
        record = EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.email_token_ttl_seconds),
        )
        self.session.add(record)
        self.session.commit()
        if purpose == "verify":
            link = f"{self.settings.public_web_url}/verify-email?token={raw}"
            self.email.send(
                to=user.email,
                subject="Verify your DocuFlow AI email",
                body=f"Confirm your email address:\n{link}\nThis link expires in one hour.",
            )
        else:
            link = f"{self.settings.public_web_url}/reset-password?token={raw}"
            self.email.send(
                to=user.email,
                subject="Reset your DocuFlow AI password",
                body=f"Reset your password:\n{link}\nIf you did not request this, ignore the message.",
            )

    def _consume_token(self, token: str, purpose: str) -> EmailToken:
        record = self.session.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(token)))
        now = datetime.now(UTC)
        if record is None or record.purpose != purpose or record.consumed_at is not None:
            raise AuthenticationError("Invalid or expired token.")
        expires = record.expires_at.replace(tzinfo=UTC) if record.expires_at.tzinfo is None else record.expires_at
        if expires < now:
            raise AuthenticationError("Invalid or expired token.")
        record.consumed_at = now
        self.session.commit()
        return record


def valid_csrf(session: SessionToken, provided: str | None) -> bool:
    if not provided:
        return False
    return digest_equals(session.csrf_token, provided)
