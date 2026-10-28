from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=200)


class TokenRequest(BaseModel):
    token: str


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    plan_slug: str
    email_verified: bool
    credits_available: int
    credits_balance: int
    credits_reserved: int


class DocumentOut(BaseModel):
    id: str
    original_filename: str
    content_type: str
    kind: str
    byte_size: int
    page_count: int | None
    origin: str
    expires_at: datetime
    created_at: datetime | None = None


class JobCreateRequest(BaseModel):
    operation: str
    document_ids: list[str]
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class JobOut(BaseModel):
    id: str
    operation: str
    status: str
    progress: int
    params: dict[str, Any]
    input_document_ids: list[str]
    result_document_ids: list[str]
    result_payload: dict[str, Any]
    error_code: str | None
    error_message: str | None
    credits_reserved: int
    created_at: datetime | None = None
    completed_at: datetime | None = None


class PlanOut(BaseModel):
    slug: str
    name: str
    monthly_credits: int
    max_file_bytes: int
    max_pages: int
    max_ai_requests_per_day: int
    features: dict[str, Any]


class LedgerOut(BaseModel):
    id: str
    amount: int
    entry_type: str
    description: str
    job_id: str | None
    created_at: datetime | None = None
