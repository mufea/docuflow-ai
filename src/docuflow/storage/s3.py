from __future__ import annotations

from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from docuflow.config import Settings
from docuflow.exceptions import NotFoundError, TransientError
from docuflow.storage.base import StoredObject


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise RuntimeError("S3 storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY.")
        self.bucket = settings.s3_bucket
        self.expires = settings.s3_signed_url_expires_seconds
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.reveal_secret(settings.s3_access_key_id),
            aws_secret_access_key=settings.reveal_secret(settings.s3_secret_access_key),
            config=Config(s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}),
        )

    def put(self, key: str, source: Path, content_type: str) -> StoredObject:
        try:
            self.client.upload_file(
                Filename=str(source),
                Bucket=self.bucket,
                Key=key,
                ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
            )
        except ClientError as exc:
            raise TransientError("Object storage upload failed.") from exc
        return StoredObject(key=key, content_type=content_type, byte_size=source.stat().st_size)

    def download(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(dest))
        except ClientError as exc:
            raise NotFoundError("Stored object was not found.") from exc
        return dest

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

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
        except ClientError:
            return None
