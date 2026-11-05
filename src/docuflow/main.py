from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse

from docuflow.ai.providers import build_ai_provider
from docuflow.api.deps import AppContext
from docuflow.api.routes import admin, auth, billing, documents, health, jobs, meta, webhooks
from docuflow.config import ProductionConfigError, Settings, get_settings
from docuflow.db import Base, create_engine_from_settings, session_factory
from docuflow.email.backend import build_email_backend
from docuflow.exceptions import DocuflowError
from docuflow.jobs.broker import build_broker
from docuflow.jobs.recovery import recover_queued_jobs
from docuflow.jobs.runner import JobRunner
from docuflow.jobs.scheduler import CleanupScheduler
from docuflow.logging import configure_logging
from docuflow.security.hosts import host_is_allowed
from docuflow.security.rate_limit import MemoryRateLimiter
from docuflow.services.seed import seed_reference_data
from docuflow.storage.factory import build_storage

logger = logging.getLogger("docuflow.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    _enforce_production_configuration(settings)
    engine = create_engine_from_settings(settings)
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        seed_reference_data(session)
    finally:
        session.close()

    storage = build_storage(settings)
    ai = build_ai_provider(settings)
    runner = JobRunner(session_factory=factory, storage=storage, settings=settings, ai=ai)
    broker = build_broker(settings, runner)
    email = build_email_backend(settings)
    scheduler = CleanupScheduler(factory, storage, settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        scheduler.start()
        recover_queued_jobs(factory, broker)
        yield
        scheduler.stop()

    app = FastAPI(
        title="DocuFlow AI API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.ctx = AppContext(
        settings=settings,
        session_factory=factory,
        storage=storage,
        broker=broker,
        email=email,
        limiter=MemoryRateLimiter(),
        runner=runner,
    )
    app.state.engine = engine

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-DocuFlow-Web-Host"],
    )

    @app.middleware("http")
    async def enforce_trusted_host(request: Request, call_next):  # type: ignore[no-untyped-def]
        if settings.is_production and not host_is_allowed(request.headers.get("host", ""), settings.trusted_host_list):
            return JSONResponse(
                status_code=400,
                content={
                    "message": (
                        "The API rejected this Host header. Set DOCUFLOW_TRUSTED_HOSTS "
                        "on the API to .onrender.com and your custom domain, then redeploy."
                    )
                },
            )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.exception_handler(DocuflowError)
    async def handle_domain_error(_request: Request, exc: DocuflowError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(jobs.router)
    app.include_router(billing.router)
    app.include_router(webhooks.router)
    app.include_router(admin.router)
    return app


def _enforce_production_configuration(settings: Settings) -> None:
    if not settings.is_production:
        return
    for item in settings.production_readiness_warnings():
        logger.warning("production_readiness_warning %s", item)
    errors = settings.production_readiness_errors()
    if not errors:
        return
    for item in errors:
        logger.error("production_readiness %s", item)
    raise ProductionConfigError(errors)


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "docuflow.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "development",
    )
