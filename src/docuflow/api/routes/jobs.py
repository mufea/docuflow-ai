from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from docuflow.api.deps import get_context, get_db, require_csrf, require_user
from docuflow.api.schemas import JobCreateRequest, JobOut
from docuflow.models import User
from docuflow.services.documents import DocumentService
from docuflow.services.jobs import JobService

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def _to_out(job) -> JobOut:
    return JobOut(
        id=job.id,
        operation=job.operation,
        status=job.status,
        progress=job.progress,
        params=_public_params(job.params or {}),
        input_document_ids=job.input_document_ids or [],
        result_document_ids=job.result_document_ids or [],
        result_payload=job.result_payload or {},
        error_code=job.error_code,
        error_message=job.error_message,
        credits_reserved=job.credits_reserved,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _public_params(params: dict) -> dict:
    clean = dict(params)
    for key in ("password", "new_password", "user_password", "owner_password"):
        if key in clean and clean[key]:
            clean[key] = "[redacted]"
    return clean


@router.get("", response_model=list[JobOut])
def list_jobs(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[JobOut]:
    ctx = get_context(request)
    service = JobService(db, DocumentService(db, ctx.storage, ctx.settings), ctx.settings)
    return [_to_out(job) for job in service.list_for_user(user)]


@router.post("", response_model=JobOut)
def create_job(
    payload: JobCreateRequest,
    request: Request,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> JobOut:
    ctx = get_context(request)
    ctx.limiter.hit(f"jobs:{user.id}", limit=40, window_seconds=60)
    service = JobService(db, DocumentService(db, ctx.storage, ctx.settings), ctx.settings)
    job = service.create(
        user,
        operation=payload.operation,
        document_ids=payload.document_ids,
        params=payload.params,
        idempotency_key=payload.idempotency_key,
    )
    if job.status == "queued":
        ctx.broker.enqueue(job.id)
    return _to_out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JobOut:
    ctx = get_context(request)
    job = JobService(db, DocumentService(db, ctx.storage, ctx.settings), ctx.settings).get_owned(user, job_id)
    return _to_out(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    request: Request,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> JobOut:
    ctx = get_context(request)
    job = JobService(db, DocumentService(db, ctx.storage, ctx.settings), ctx.settings).cancel(user, job_id)
    return _to_out(job)
