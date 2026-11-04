from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

logger = logging.getLogger("docuflow.health")

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "docuflow-api"}


@router.get("/ready")
def ready(request: Request) -> dict[str, object]:
    ctx = request.app.state.ctx
    checks: dict[str, bool] = {}
    session = ctx.session_factory()
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.warning("ready_database_failed")
        checks["database"] = False
    finally:
        session.close()
    if ctx.settings.job_broker == "rq":
        try:
            from redis import Redis

            Redis.from_url(ctx.settings.redis_url).ping()
            checks["redis"] = True
        except Exception:
            logger.warning("ready_redis_failed")
            checks["redis"] = False
    else:
        checks["redis"] = True
    try:
        ctx.storage.ping()
        checks["storage"] = True
    except Exception:
        logger.warning("ready_storage_failed")
        checks["storage"] = False
    rq_workers = 0
    if ctx.settings.job_broker == "rq":
        count_fn = getattr(ctx.broker, "active_worker_count", None)
        if callable(count_fn):
            try:
                rq_workers = int(count_fn())
            except Exception:
                rq_workers = 0
    ok = all(checks.values())
    return {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "broker": ctx.settings.job_broker,
        "rq_workers": rq_workers,
    }
