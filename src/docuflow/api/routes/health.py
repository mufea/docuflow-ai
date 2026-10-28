from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

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
        checks["database"] = False
    finally:
        session.close()
    if ctx.settings.job_broker == "rq":
        try:
            from redis import Redis

            Redis.from_url(ctx.settings.redis_url).ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
    else:
        checks["redis"] = True
    checks["storage"] = True
    ok = all(checks.values())
    return {"status": "ready" if ok else "degraded", "checks": checks}
