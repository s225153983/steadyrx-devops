"""Health, version and metrics endpoints used by Jenkins and Prometheus."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["operations"])


@router.get("/health/live")
def live() -> dict:
    """Liveness. The process is up and serving HTTP."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request, response: Response) -> dict:
    """Readiness. The database answers, so the app can take traffic."""
    ok = request.app.state.service.db.ping()
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ok else "degraded", "database": ok}


@router.get("/version")
def version(request: Request) -> dict:
    s = request.app.state.settings
    return {"version": s.app_version, "environment": s.app_env,
            "build_sha": s.build_sha}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
