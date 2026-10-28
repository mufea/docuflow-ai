from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from docuflow.ai.chunking import chunk_pages, retrieve
from docuflow.ai.providers import AIProvider, validate_structured
from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.conversion.engines import ConversionService
from docuflow.exceptions import DocuflowError, EncryptedPdfError, UnsupportedOperationError
from docuflow.models import Document, Job, User
from docuflow.ocr.engine import OcrEngine
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.workdir import work_directory
from docuflow.services.documents import DocumentService
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.jobs")


class JobRunner:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        settings: Settings,
        ai: AIProvider,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.settings = settings
        self.ai = ai
        self.engine = PdfEngine(
            max_bytes=settings.max_upload_bytes,
            max_pages=settings.max_pages,
            max_images=settings.max_images_per_job,
        )
        self.conversion = ConversionService()
        self.ocr = OcrEngine(enabled=settings.ocr_enabled)

    def process(self, job_id: str) -> None:
        session = self.session_factory()
        try:
            job = session.get(Job, job_id)
            if job is None:
                logger.warning("job_missing id=%s", job_id)
                return
            if job.status in {"completed", "cancelled"}:
                return
            job.status = "processing"
            job.started_at = datetime.now(UTC)
            job.attempt += 1
            job.progress = 5
            session.commit()
            user = session.get(User, job.user_id)
            if user is None:
                raise UnsupportedOperationError("Job owner no longer exists.")
            try:
                payload = self._execute(session, job, user)
                job.result_payload = payload
                job.status = "completed"
                job.progress = 100
                job.completed_at = datetime.now(UTC)
                CreditService(session).settle(user, job.credits_reserved, job_id=job.id)
                session.commit()
            except DocuflowError as exc:
                session.rollback()
                self._fail(session, job_id, exc.code, exc.message, refund=True)
            except Exception:
                session.rollback()
                logger.exception("job_failed id=%s", job_id)
                self._fail(session, job_id, "internal_error", "Processing failed.", refund=True)
        finally:
            session.close()

    def _fail(self, session: Session, job_id: str, code: str, message: str, *, refund: bool) -> None:
        job = session.get(Job, job_id)
        if job is None:
            return
        user = session.get(User, job.user_id)
        job.status = "failed"
        job.error_code = code
        job.error_message = message
        job.completed_at = datetime.now(UTC)
        if refund and user and job.credits_reserved:
            CreditService(session).refund_reservation(user, job.credits_reserved, job_id=job.id)
        session.commit()

    def _execute(self, session: Session, job: Job, user: User) -> dict[str, Any]:
        docs = [session.get(Document, item) for item in job.input_document_ids]
        if any(item is None or item.deleted_at is not None for item in docs):
            raise UnsupportedOperationError("One or more input documents are missing.")
        if any(item.user_id != user.id for item in docs if item is not None):
            raise UnsupportedOperationError("Input documents do not belong to this account.")
        document_service = DocumentService(session, self.storage, self.settings)
        password = job.params.get("password")
        if password:
            logger.info("job_uses_password id=%s", job.id)
        with work_directory(parent=self.settings.temp_dir) as work:
            local_paths = []
            for doc in docs:
                assert doc is not None
                dest = work / f"{doc.id}{Path(doc.original_filename).suffix or '.bin'}"
                self.storage.download(doc.storage_key, dest)
                local_paths.append(dest)
            job.progress = 25
            session.commit()
            outputs, extra = self._run_operation(job, local_paths, work, password)
            job.progress = 80
            session.commit()
            result_ids: list[str] = []
            stored_names: list[str] = []
            for output in outputs:
                stored = document_service.store_result(
                    user,
                    output,
                    original_filename=output.name,
                    origin=f"job:{job.operation}",
                )
                result_ids.append(stored.id)
                stored_names.append(stored.original_filename)
            job.result_document_ids = result_ids
            extra["result_files"] = stored_names
            return extra

    def _run_operation(
        self,
        job: Job,
        inputs: list[Path],
        work: Path,
        password: str | None,
    ) -> tuple[list[Path], dict[str, Any]]:
        op = job.operation
        params = job.params
        out_dir = work / "out"
        out_dir.mkdir()
        engine = self.engine

        if op == "merge":
            dest = out_dir / "merged.pdf"
            result = engine.merge(inputs, dest, password=password)
            return result.outputs, {"warnings": result.warnings, **result.metadata}
        if op == "split":
            result = engine.split(inputs[0], params.get("ranges") or "1", out_dir, password=password)
            return result.outputs, result.metadata
        if op == "extract":
            dest = out_dir / "extracted.pdf"
            result = engine.extract_pages(
                inputs[0], params.get("pages") or params.get("ranges") or [1], dest, password=password
            )
            return result.outputs, result.metadata
        if op == "reorder":
            dest = out_dir / "reordered.pdf"
            result = engine.reorder(inputs[0], params.get("order") or [], dest, password=password)
            return result.outputs, result.metadata
        if op == "rotate":
            dest = out_dir / "rotated.pdf"
            rotations = {int(k): int(v) for k, v in (params.get("rotations") or {}).items()}
            result = engine.rotate(inputs[0], rotations, dest, password=password)
            return result.outputs, result.metadata
        if op == "delete_pages":
            dest = out_dir / "edited.pdf"
            result = engine.delete_pages(inputs[0], params.get("pages") or [], dest, password=password)
            return result.outputs, result.metadata
        if op == "compress":
            dest = out_dir / "compressed.pdf"
            result = engine.compress(inputs[0], dest, level=params.get("level") or "medium", password=password)
            return result.outputs, {**result.metadata, "warnings": result.warnings}
        if op == "images_to_pdf":
            dest = out_dir / "images.pdf"
            result = engine.images_to_pdf(inputs, dest)
            return result.outputs, result.metadata
        if op == "pdf_to_images":
            result = engine.pdf_to_images(
                inputs[0],
                out_dir,
                image_format=params.get("format") or "png",
                dpi=int(params.get("dpi") or 144),
                pages=params.get("pages"),
                password=password,
            )
            return result.outputs, result.metadata
        if op == "extract_text":
            result = engine.extract_text(inputs[0], pages=params.get("pages"), password=password)
            return [], {
                "text": result.metadata.get("text"),
                "pages": result.metadata.get("pages"),
                "warnings": result.warnings,
            }
        if op == "protect":
            dest = out_dir / "protected.pdf"
            new_password = params.get("new_password")
            if not new_password:
                raise EncryptedPdfError("A new password is required to protect the PDF.")
            result = engine.protect(inputs[0], dest, user_password=new_password, password=password)
            return result.outputs, result.metadata
        if op == "unlock":
            dest = out_dir / "unlocked.pdf"
            if not password:
                raise EncryptedPdfError("A password is required to remove PDF encryption.")
            result = engine.unlock(inputs[0], dest, password=password)
            return result.outputs, result.metadata
        if op == "thumbnails":
            result = engine.thumbnails(inputs[0], out_dir, pages=params.get("pages"), password=password)
            return result.outputs, result.metadata
        if op == "pdf_to_docx":
            dest = out_dir / "converted.docx"
            converted = self.conversion.pdf_to_docx(inputs[0], dest)
            return converted.outputs, {
                "output_format": converted.output_format,
                "engine": converted.engine,
                "limitations": converted.limitations,
            }
        if op == "pdf_to_xlsx":
            dest = out_dir / "tables.xlsx"
            converted = self.conversion.pdf_to_xlsx(inputs[0], dest)
            return converted.outputs, {
                "output_format": converted.output_format,
                "engine": converted.engine,
                "limitations": converted.limitations,
                **converted.metadata,
            }
        if op == "docx_to_pdf":
            dest = out_dir / "converted.pdf"
            converted = self.conversion.docx_to_pdf(inputs[0], dest)
            return converted.outputs, {
                "output_format": converted.output_format,
                "engine": converted.engine,
                "limitations": converted.limitations,
            }
        if op == "ocr":
            ocr = self.ocr.run(inputs[0], password=password, pages=params.get("pages"))
            return [], {
                "pages": [{"page": item.page, "text": item.text} for item in ocr.pages],
                "engine": ocr.engine,
                "limitations": ocr.limitations,
            }
        if op in {"summarize", "ask", "extract_structured"}:
            return self._run_ai(job, inputs[0], password)
        raise UnsupportedOperationError(f"Unknown operation {op}.")

    def _run_ai(self, job: Job, source: Path, password: str | None) -> tuple[list[Path], dict[str, Any]]:
        extracted = self.engine.extract_text(source, pages=job.params.get("pages"), password=password)
        pages = extracted.metadata.get("pages") or []
        chunks = chunk_pages(pages, max_chars=min(1500, self.settings.ai_max_input_chars))
        if job.operation == "ask":
            query = str(job.params.get("question") or "")
            chunks = retrieve(chunks, query)
            instruction = f"Question: {query}"
            schema = None
        elif job.operation == "extract_structured":
            schema = job.params.get("schema") or {
                "type": "object",
                "properties": {"title": {"type": "string"}, "dates": {"type": "array"}},
            }
            instruction = "Extract structured fields from the excerpts. Use null when not present."
        else:
            instruction = "Summarize the excerpts. Mention page numbers only for statements present in those excerpts."
            schema = None
        response = self.ai.generate(instruction=instruction, chunks=chunks, schema=schema)
        payload: dict[str, Any] = {
            "text": response.text,
            "citations": response.citations,
            "provider": response.provider,
            "model": response.model,
            "data_processing": {
                "text_extracted_locally": True,
                "document_uploaded_to_provider": response.provider != "mock",
                "provider": response.provider,
            },
        }
        if schema:
            payload["structured"] = (
                validate_structured(response.text, schema)
                if response.provider != "mock"
                else __import__("json").loads(response.text)
            )
        return [], payload
