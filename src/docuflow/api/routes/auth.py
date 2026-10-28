from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from docuflow.api.deps import get_context, get_db, get_settings, require_csrf, require_user
from docuflow.api.schemas import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdate,
    RegisterRequest,
    TokenRequest,
    UserOut,
)
from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.models import CreditAccount, User
from docuflow.security.rate_limit import MemoryRateLimiter
from docuflow.services.auth import AuthService
from docuflow.services.documents import DocumentService

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _set_session_cookies(response: Response, settings: Settings, raw: str, csrf: str) -> None:
    secure = settings.cookie_secure or settings.is_production
    response.set_cookie(
        settings.session_cookie_name,
        raw,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        httponly=False,
        secure=secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def _user_out(session: Session, user: User) -> UserOut:
    account = session.get(CreditAccount, user.id)
    if account is None:
        account = CreditService(session).ensure_account(user)
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        plan_slug=user.plan_slug,
        email_verified=user.email_verified_at is not None,
        credits_available=account.balance - account.reserved,
        credits_balance=account.balance,
        credits_reserved=account.reserved,
    )


@router.post("/register", response_model=UserOut)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    ctx = get_context(request)
    limiter: MemoryRateLimiter = ctx.limiter
    limiter.hit(f"register:{request.client.host if request.client else 'unknown'}", limit=5, window_seconds=60)
    auth = AuthService(db, settings, ctx.email)
    user = auth.register(email=payload.email, password=payload.password, name=payload.name)
    return _user_out(db, user)


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    ctx = get_context(request)
    ctx.limiter.hit(f"login:{request.client.host if request.client else 'unknown'}", limit=10, window_seconds=60)
    auth = AuthService(db, settings, ctx.email)
    user, raw, csrf = auth.login(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, settings, raw, csrf)
    return _user_out(db, user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    auth = AuthService(db, settings, get_context(request).email)
    auth.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user), db: Session = Depends(get_db)) -> UserOut:
    return _user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.name:
        user.name = payload.name
        db.commit()
    return _user_out(db, user)


@router.delete("/me")
def delete_me(
    request: Request,
    response: Response,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    ctx = get_context(request)
    documents = DocumentService(db, ctx.storage, settings)
    for document in documents.list_for_user(user):
        documents.delete(user, document.id)
    AuthService(db, settings, ctx.email).delete_account(user)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    get_context(request).limiter.hit("forgot", limit=8, window_seconds=60)
    AuthService(db, settings, get_context(request).email).request_password_reset(payload.email)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    AuthService(db, settings, get_context(request).email).reset_password(payload.token, payload.password)
    return {"ok": True}


@router.post("/verify-email")
def verify_email(
    payload: TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    AuthService(db, settings, get_context(request).email).verify_email(payload.token)
    return {"ok": True}
