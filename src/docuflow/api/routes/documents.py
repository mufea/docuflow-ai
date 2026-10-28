from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from docuflow.api.deps import get_context, get_db, get_settings, require_csrf, require_user
from docuflow.api.schemas import DocumentOut
from docuflow.config import Settings
from docuflow.exceptions import FileTooLargeError, ValidationError
from docuflow.models import User
from docuflow.services.documents import DocumentService

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _to_out(document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        original_filename=document.original_filename,
        content_type=document.content_type,
        kind=document.kind,
        byte_size=document.byte_size,
        page_count=document.page_count,
        origin=document.origin,
        expires_at=document.expires_at,
        created_at=document.created_at,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> list[DocumentOut]:
    ctx = get_context(request)
    docs = DocumentService(db, ctx.storage, ctx.settings).list_for_user(user)
    return [_to_out(item) for item in docs]


@router.post("", response_model=DocumentOut)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentOut:
    ctx = get_context(request)
    ctx.limiter.hit(f"upload:{user.id}", limit=30, window_seconds=60)
    if not file.filename:
        raise ValidationError("A file name is required.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise FileTooLargeError("File exceeds the configured upload limit.")
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    try:
        document = DocumentService(db, ctx.storage, settings).store_upload(user, tmp_path, file.filename)
    finally:
        tmp_path.unlink(missing_ok=True)
    return _to_out(document)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    document = DocumentService(db, get_context(request).storage, get_context(request).settings).get_owned(
        user, document_id
    )
    return _to_out(document)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    ctx = get_context(request)
    service = DocumentService(db, ctx.storage, ctx.settings)
    document = service.get_owned(user, document_id)
    signed = ctx.storage.signed_url(
        document.storage_key,
        expires_seconds=ctx.settings.s3_signed_url_expires_seconds,
        filename=document.original_filename,
    )
    if signed:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(signed, status_code=302)  # type: ignore[return-value]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(document.original_filename).suffix)
    tmp.close()
    dest = Path(tmp.name)
    ctx.storage.download(document.storage_key, dest)
    return FileResponse(
        dest,
        filename=document.original_filename,
        media_type=document.content_type,
        background=BackgroundTask(dest.unlink, missing_ok=True),
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    request: Request,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    DocumentService(db, get_context(request).storage, get_context(request).settings).delete(user, document_id)
    return {"ok": True}
