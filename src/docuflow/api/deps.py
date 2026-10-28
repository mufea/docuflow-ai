from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from docuflow.config import Settings
from docuflow.email.backend import EmailBackend
from docuflow.exceptions import AuthenticationError, AuthorizationError
from docuflow.jobs.broker import JobBroker
from docuflow.jobs.runner import JobRunner
from docuflow.models import SessionToken, User
from docuflow.security.rate_limit import MemoryRateLimiter
from docuflow.services.auth import AuthService, valid_csrf
from docuflow.storage.base import ObjectStorage


@dataclass
class AppContext:
    settings: Settings
    session_factory: sessionmaker[Session]
    storage: ObjectStorage
    broker: JobBroker
    email: EmailBackend
    limiter: MemoryRateLimiter
    runner: JobRunner


def get_context(request: Request) -> AppContext:
    return request.app.state.ctx


def get_db(request: Request) -> Generator[Session, None, None]:
    session: Session = request.app.state.ctx.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.ctx.settings


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> tuple[User, SessionToken]:
    raw = request.cookies.get(settings.session_cookie_name)
    auth = AuthService(db, settings, request.app.state.ctx.email)
    loaded = auth.user_from_session(raw)
    if loaded is None:
        raise AuthenticationError("Sign in to continue.")
    return loaded


def require_user(auth: tuple[User, SessionToken] = Depends(current_user)) -> User:
    return auth[0]


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise AuthorizationError("Administrator access required.")
    return user


def require_csrf(
    request: Request,
    auth: tuple[User, SessionToken] = Depends(current_user),
) -> User:
    user, token = auth
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return user
    header = request.headers.get("x-csrf-token")
    if not valid_csrf(token, header):
        raise AuthorizationError("Invalid CSRF token.")
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.ctx.settings.cors_origin_list:
        raise AuthorizationError("Invalid request origin.")
    return user
