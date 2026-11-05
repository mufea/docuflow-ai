from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, NoReturn

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, DocuflowError, NotFoundError, TransientError
from docuflow.storage.base import StoredObject
from docuflow.storage.timeouts import storage_call_budget

logger = logging.getLogger("docuflow.storage")

_TIMEOUT_ERRORS = (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError)
_TRANSFER = TransferConfig(num_download_attempts=1)

S3ErrorKind = Literal["missing", "authorization", "transient", "permanent"]

_MISSING_CODES = frozenset({"NoSuchKey", "NotFound", "NoSuchVersion", "NoSuchUpload", "404"})
_AUTH_CODES = frozenset(
    {
        "AccessDenied",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "InvalidToken",
        "ExpiredToken",
        "AuthFailure",
        "InvalidClientTokenId",
        "UnrecognizedClientException",
        "AccountProblem",
        "OptInRequired",
    }
)
_TRANSIENT_CODES = frozenset(
    {
        "SlowDown",
        "ServiceUnavailable",
        "InternalError",
        "InternalFailure",
        "Throttling",
        "ThrottlingException",
        "RequestTimeout",
        "RequestTimeoutException",
        "PriorRequestNotComplete",
        "RequestLimitExceeded",
        "503",
        "500",
        "502",
        "504",
        "429",
    }
)
_PERMANENT_CODES = frozenset(
    {
        "NoSuchBucket",
        "InvalidBucketName",
        "PermanentRedirect",
        "IllegalLocationConstraintException",
        "InvalidArgument",
        "InvalidRequest",
        "MalformedXML",
    }
)

_SAFE_MESSAGES: dict[S3ErrorKind, str] = {
    "missing": "Stored object was not found.",
    "authorization": "Object storage access was denied.",
    "transient": "Object storage is temporarily unavailable.",
    "permanent": "Object storage request failed.",
}


def classify_s3_client_error(exc: ClientError) -> tuple[S3ErrorKind, str, int | None]:
    response = getattr(exc, "response", None) or {}
    error = response.get("Error") or {}
    code = str(error.get("Code") or "").strip()
    status_raw = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    try:
        status = int(status_raw) if status_raw is not None else None
    except (TypeError, ValueError):
        status = None
    if code in _AUTH_CODES or status in (401, 403):
        kind: S3ErrorKind = "authorization"
    elif code in _PERMANENT_CODES:
        kind = "permanent"
    elif code in _MISSING_CODES or status == 404:
        kind = "missing"
    elif code in _TRANSIENT_CODES or (status is not None and (status >= 500 or status == 429)):
        kind = "transient"
    else:
        kind = "permanent"
    return kind, code or "unknown", status


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise RuntimeError("S3 storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY.")
        self.bucket = settings.s3_bucket
        self.expires = settings.s3_signed_url_expires_seconds
        budget = storage_call_budget(settings.storage_delete_lease_minutes)
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.reveal_secret(settings.s3_access_key_id),
            aws_secret_access_key=settings.reveal_secret(settings.s3_secret_access_key),
            config=Config(
                connect_timeout=budget.connect_timeout_seconds,
                read_timeout=budget.read_timeout_seconds,
                retries=budget.botocore_retries,
                s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            ),
        )

    def put(self, key: str, source: Path, content_type: str) -> StoredObject:
        try:
            self.client.upload_file(
                Filename=str(source),
                Bucket=self.bucket,
                Key=key,
                ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
                Config=_TRANSFER,
            )
        except _TIMEOUT_ERRORS as exc:
            self._log_timeout("upload")
            raise TransientError("Object storage upload timed out.") from exc
        except ClientError as exc:
            self._raise_client_error("upload", exc, missing_as="error")
        except BotoCoreError as exc:
            raise TransientError("Object storage is temporarily unavailable.") from exc
        return StoredObject(key=key, content_type=content_type, byte_size=source.stat().st_size)

    def download(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(dest), Config=_TRANSFER)
        except _TIMEOUT_ERRORS as exc:
            self._log_timeout("download")
            raise TransientError("Object storage download timed out.") from exc
        except ClientError as exc:
            self._raise_client_error("download", exc, missing_as="missing")
        except BotoCoreError as exc:
            raise TransientError("Object storage is temporarily unavailable.") from exc
        return dest

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except _TIMEOUT_ERRORS as exc:
            self._log_timeout("delete")
            raise TransientError("Object storage delete timed out.") from exc
        except ClientError as exc:
            kind, _, _ = classify_s3_client_error(exc)
            if kind == "missing":
                self._log_classified("delete", exc)
                return
            self._raise_client_error("delete", exc, missing_as="missing")
        except BotoCoreError as exc:
            raise TransientError("Object storage is temporarily unavailable.") from exc

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except _TIMEOUT_ERRORS as exc:
            self._log_timeout("exists")
            raise TransientError("Object storage is temporarily unavailable.") from exc
        except ClientError as exc:
            kind, _, _ = classify_s3_client_error(exc)
            if kind == "missing":
                self._log_classified("exists", exc)
                return False
            self._raise_client_error("exists", exc, missing_as="missing")
        except BotoCoreError as exc:
            raise TransientError("Object storage is temporarily unavailable.") from exc

    def signed_url(self, key: str, *, expires_seconds: int, filename: str | None = None) -> str | None:
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_seconds,
            )
        except (ClientError, BotoCoreError):
            logger.warning("storage_s3_error operation=signed_url classification=permanent code=unknown http_status=0")
            return None

    def ping(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except _TIMEOUT_ERRORS as exc:
            self._log_timeout("ping")
            raise TransientError("Object storage is temporarily unavailable.") from exc
        except ClientError as exc:
            self._raise_client_error("ping", exc, missing_as="error")
        except BotoCoreError as exc:
            raise TransientError("Object storage is temporarily unavailable.") from exc

    def _log_timeout(self, operation: str) -> None:
        logger.warning("storage_s3_error operation=%s classification=timeout code=timeout http_status=0", operation)

    def _log_classified(self, operation: str, exc: ClientError) -> None:
        kind, code, status = classify_s3_client_error(exc)
        logger.warning(
            "storage_s3_error operation=%s classification=%s code=%s http_status=%s",
            operation,
            kind,
            code,
            0 if status is None else status,
        )

    def _raise_client_error(
        self,
        operation: str,
        exc: ClientError,
        *,
        missing_as: Literal["missing", "error"],
    ) -> NoReturn:
        kind, _, _ = classify_s3_client_error(exc)
        self._log_classified(operation, exc)
        if kind == "missing":
            if missing_as == "missing":
                raise NotFoundError(_SAFE_MESSAGES["missing"]) from exc
            kind = "permanent"
        if kind == "authorization":
            raise AuthorizationError(_SAFE_MESSAGES["authorization"]) from exc
        if kind == "transient":
            raise TransientError(_SAFE_MESSAGES["transient"]) from exc
        raise DocuflowError(_SAFE_MESSAGES["permanent"]) from exc
