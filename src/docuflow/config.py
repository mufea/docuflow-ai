from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from docuflow.dsn import normalize_database_url
from docuflow.security.hosts import origin_variants


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    env: Literal["development", "test", "production"] = Field(default="development", alias="DOCUFLOW_ENV")
    secret_key: SecretStr = Field(
        default=SecretStr("dev-only-change-me-use-32-plus-chars!!"),
        alias="DOCUFLOW_SECRET_KEY",
    )
    api_host: str = Field(default="127.0.0.1", alias="DOCUFLOW_API_HOST")
    api_port: int = Field(default=43124, alias="DOCUFLOW_API_PORT")
    public_api_url: str = Field(default="http://127.0.0.1:43124", alias="DOCUFLOW_PUBLIC_API_URL")
    public_web_url: str = Field(default="http://127.0.0.1:43123", alias="DOCUFLOW_PUBLIC_WEB_URL")
    cors_origins: str = Field(
        default="http://127.0.0.1:43123,http://localhost:43123",
        alias="DOCUFLOW_CORS_ORIGINS",
    )
    trusted_hosts: str = Field(default="127.0.0.1,localhost", alias="DOCUFLOW_TRUSTED_HOSTS")

    database_url: str = Field(
        default="sqlite+pysqlite:///./data/docuflow.db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    job_broker: Literal["inline", "rq"] = Field(default="inline", alias="JOB_BROKER")
    rq_queue_name: str = Field(default="docuflow", alias="RQ_QUEUE_NAME")
    worker_timeout_seconds: int = Field(default=300, alias="WORKER_TIMEOUT_SECONDS")
    worker_concurrency: int = Field(default=2, alias="WORKER_CONCURRENCY")

    storage_backend: Literal["filesystem", "s3"] = Field(default="filesystem", alias="STORAGE_BACKEND")
    storage_local_path: str = Field(default="./data/storage", alias="STORAGE_LOCAL_PATH")
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_region: str = Field(default="auto", alias="S3_REGION")
    s3_bucket: str = Field(default="docuflow-documents", alias="S3_BUCKET")
    s3_access_key_id: SecretStr | None = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr | None = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    s3_force_path_style: bool = Field(default=True, alias="S3_FORCE_PATH_STYLE")
    s3_signed_url_expires_seconds: int = Field(default=600, alias="S3_SIGNED_URL_EXPIRES_SECONDS")

    max_upload_bytes: int = Field(default=50 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    max_pages: int = Field(default=400, alias="MAX_PAGES")
    max_images_per_job: int = Field(default=40, alias="MAX_IMAGES_PER_JOB")
    file_retention_hours: int = Field(default=24, alias="FILE_RETENTION_HOURS")
    result_retention_hours: int = Field(default=48, alias="RESULT_RETENTION_HOURS")
    temp_dir: str | None = Field(default=None, alias="TEMP_DIR")

    session_cookie_name: str = Field(default="df_session", alias="SESSION_COOKIE_NAME")
    csrf_cookie_name: str = Field(default="df_csrf", alias="CSRF_COOKIE_NAME")
    session_ttl_seconds: int = Field(default=14 * 24 * 3600, alias="SESSION_TTL_SECONDS")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(default="lax", alias="COOKIE_SAMESITE")

    email_backend: Literal["console", "smtp"] = Field(default="console", alias="EMAIL_BACKEND")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: SecretStr | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="DocuFlow AI <no-reply@localhost>", alias="SMTP_FROM")
    email_token_ttl_seconds: int = Field(default=3600, alias="EMAIL_TOKEN_TTL_SECONDS")

    default_plan: str = Field(default="free", alias="DEFAULT_PLAN")
    allow_negative_credits: bool = Field(default=False, alias="ALLOW_NEGATIVE_CREDITS")

    ai_provider: Literal["mock", "openai_compatible"] = Field(default="mock", alias="AI_PROVIDER")
    ai_api_key: SecretStr | None = Field(default=None, alias="AI_API_KEY")
    ai_base_url: str | None = Field(default=None, alias="AI_BASE_URL")
    ai_model: str = Field(default="mock-docuflow", alias="AI_MODEL")
    ai_timeout_seconds: int = Field(default=30, alias="AI_TIMEOUT_SECONDS")
    ai_max_input_chars: int = Field(default=120_000, alias="AI_MAX_INPUT_CHARS")
    ocr_enabled: bool = Field(default=True, alias="OCR_ENABLED")

    stripe_secret_key: SecretStr | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: SecretStr | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_pro: str | None = Field(default=None, alias="STRIPE_PRICE_PRO")
    stripe_price_business: str | None = Field(default=None, alias="STRIPE_PRICE_BUSINESS")
    midtrans_server_key: SecretStr | None = Field(default=None, alias="MIDTRANS_SERVER_KEY")
    midtrans_client_key: str | None = Field(default=None, alias="MIDTRANS_CLIENT_KEY")
    midtrans_is_production: bool = Field(default=False, alias="MIDTRANS_IS_PRODUCTION")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    @field_validator("secret_key")
    @classmethod
    def _secret_not_empty(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 16:
            raise ValueError("DOCUFLOW_SECRET_KEY must be at least 16 characters.")
        return value

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @model_validator(mode="after")
    def _fill_render_public_api_url(self) -> Settings:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if render_url and (
            self.public_api_url.startswith("http://127.0.0.1") or self.public_api_url.startswith("http://localhost")
        ):
            self.public_api_url = render_url
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins: list[str] = []
        seen: set[str] = set()
        for raw in (*self.cors_origins.split(","), self.public_web_url):
            for item in origin_variants(raw):
                if item not in seen:
                    seen.add(item)
                    origins.append(item)
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        if self.env == "production":
            return r"https://([A-Za-z0-9-]+\.)*onrender\.com"
        return None

    @property
    def trusted_host_list(self) -> list[str]:
        hosts: list[str] = []
        for item in self.trusted_hosts.split(","):
            value = item.strip()
            if value:
                hosts.append(value)
        candidates = [
            self.public_api_url,
            self.public_web_url,
            os.environ.get("RENDER_EXTERNAL_URL", ""),
            *self.cors_origin_list,
        ]
        for raw in candidates:
            host = urlparse(raw).hostname if raw else None
            if host:
                hosts.append(host)
        render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
        if render_host:
            hosts.append(render_host)
        on_render = bool(os.environ.get("RENDER")) or any(host.endswith(".onrender.com") for host in hosts)
        if self.env == "production" or on_render:
            hosts.append(".onrender.com")
        unique: list[str] = []
        seen: set[str] = set()
        for host in hosts:
            if host not in seen:
                seen.add(host)
                unique.append(host)
        return unique

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def reveal_secret(self, value: SecretStr | None) -> str | None:
        if value is None:
            return None
        return value.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
