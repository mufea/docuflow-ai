from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.billing.ledger import CreditService
from docuflow.billing.plans import DEFAULT_OPERATION_COSTS
from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, ConflictError, JobStateError, NotFoundError, ValidationError
from docuflow.jobs.operations import JOB_OPERATIONS
from docuflow.models import Job, OperationCost, Plan, User
from docuflow.services.documents import DocumentService


class JobService:
    def __init__(self, session: Session, documents: DocumentService, settings: Settings) -> None:
        self.session = session
        self.documents = documents
        self.settings = settings

    def create(
        self,
        user: User,
        *,
        operation: str,
        document_ids: list[str],
        params: dict[str, object],
        idempotency_key: str | None,
    ) -> Job:
        if operation not in JOB_OPERATIONS:
            raise ValidationError("Unknown processing operation.")
        if idempotency_key:
            existing = self.session.scalar(
                select(Job).where(Job.user_id == user.id, Job.idempotency_key == idempotency_key)
            )
            if existing:
                return existing
        docs = [self.documents.get_owned(user, item) for item in document_ids]
        if not docs:
            raise ValidationError("At least one document is required.")
        plan = self.session.get(Plan, user.plan_slug)
        for doc in docs:
            if plan and doc.byte_size > plan.max_file_bytes:
                raise ValidationError("File exceeds the size limit for your plan.")
            if plan and doc.page_count and doc.page_count > plan.max_pages:
                raise ValidationError("Document exceeds the page limit for your plan.")
        cost_row = self.session.get(OperationCost, operation)
        cost = cost_row.credits if cost_row else DEFAULT_OPERATION_COSTS.get(operation, 1)
        job = Job(
            user_id=user.id,
            operation=operation,
            status="queued",
            params=params,
            input_document_ids=document_ids,
            idempotency_key=idempotency_key,
            credits_reserved=cost,
        )
        self.session.add(job)
        self.session.flush()
        CreditService(self.session).reserve(user, cost, job_id=job.id)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_owned(self, user: User, job_id: str) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        if job.user_id != user.id and user.role != "admin":
            raise AuthorizationError("You cannot access this job.")
        return job

    def list_for_user(self, user: User) -> list[Job]:
        return list(self.session.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())))

    def cancel(self, user: User, job_id: str) -> Job:
        job = self.get_owned(user, job_id)
        if job.status not in {"queued"}:
            raise JobStateError("Only queued jobs can be cancelled.")
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        CreditService(self.session).refund_reservation(user, job.credits_reserved, job_id=job.id)
        self.session.commit()
        return job

    def mark_duplicate_conflict(self) -> None:
        raise ConflictError("A job with this idempotency key already exists.")
