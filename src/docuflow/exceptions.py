"""Typed application errors. Messages are safe for API clients; no secrets."""

from __future__ import annotations


class DocuflowError(Exception):
    code = "internal_error"
    http_status = 500
    retryable = False

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"error": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class InvalidFileError(DocuflowError):
    code = "invalid_file"
    http_status = 400


class InvalidPdfError(InvalidFileError):
    code = "invalid_pdf"


class EncryptedPdfError(DocuflowError):
    code = "encrypted_pdf"
    http_status = 400


class EmptyDocumentError(DocuflowError):
    code = "empty_document"
    http_status = 400


class PageRangeError(DocuflowError):
    code = "invalid_page_range"
    http_status = 400


class FileTooLargeError(DocuflowError):
    code = "file_too_large"
    http_status = 413


class TooManyPagesError(DocuflowError):
    code = "too_many_pages"
    http_status = 400


class UnsupportedFormatError(DocuflowError):
    code = "unsupported_format"
    http_status = 415


class UnsupportedOperationError(DocuflowError):
    code = "unsupported_operation"
    http_status = 400


class EngineUnavailableError(DocuflowError):
    code = "engine_unavailable"
    http_status = 503


class AuthenticationError(DocuflowError):
    code = "unauthenticated"
    http_status = 401


class AuthorizationError(DocuflowError):
    code = "forbidden"
    http_status = 403


class NotFoundError(DocuflowError):
    code = "not_found"
    http_status = 404


class RateLimitError(DocuflowError):
    code = "rate_limited"
    http_status = 429
    retryable = True


class InsufficientCreditsError(DocuflowError):
    code = "insufficient_credits"
    http_status = 402


class ConflictError(DocuflowError):
    code = "conflict"
    http_status = 409


class JobStateError(DocuflowError):
    code = "invalid_job_state"
    http_status = 409


class TransientError(DocuflowError):
    code = "transient_error"
    http_status = 503
    retryable = True


class ValidationError(DocuflowError):
    code = "validation_error"
    http_status = 422
