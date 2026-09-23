"""Application factory and HTTP middleware."""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.database import Database, seed_demo_data
from app.metrics import APP_INFO, LATENCY, REQUESTS
from app.routers import auth, clinical, ops
from app.security import decode_token
from app.services import SteadyRxService

logger = logging.getLogger("steadyrx")


class JsonFormatter(logging.Formatter):
    """One JSON object per log line so log tools can parse it."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {"level": record.levelname, "logger": record.name,
                 "message": record.getMessage()}
        entry.update(getattr(record, "extra_fields", {}))
        return json.dumps(entry)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


def _seed_medicines(service: SteadyRxService) -> None:
    """Give the demo patients a medicine history that matches the prototype."""
    if service.list_medicines(1):
        return
    change = date.today() - timedelta(days=9)
    service.add_medicine(1, "Temazepam 10 mg", "10 mg at night",
                         change - timedelta(days=200), "seed")
    service.add_medicine(1, "Furosemide 40 mg", "40 mg mane",
                         change - timedelta(days=120), "seed")
    service.add_medicine(1, "Oxycodone 5 mg", "5 mg twice daily", change, "seed")
    service.add_medicine(2, "Atorvastatin 20 mg", "20 mg nocte", change, "seed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application for one environment."""
    settings = settings or load_settings()
    _configure_logging(settings.log_level)

    db = Database(settings.database_path)
    service = SteadyRxService(db, settings)
    if settings.seed_demo_data:
        seed_demo_data(db)
        _seed_medicines(service)
    service.refresh_gauges()

    app = FastAPI(title="SteadyRx API", version=settings.app_version,
                  description="Early warning of medicine-related falls")
    app.state.settings = settings
    app.state.service = service
    app.state.decode = lambda token: decode_token(token, settings.jwt_secret)
    APP_INFO.info({"version": settings.app_version,
                   "environment": settings.app_env,
                   "build_sha": settings.build_sha})

    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware,
                           allow_origins=settings.allowed_origins,
                           allow_methods=["GET", "POST"],
                           allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            template = getattr(route, "path", "unmatched")
            elapsed = time.perf_counter() - start
            REQUESTS.labels(request.method, template, str(status_code)).inc()
            LATENCY.labels(template).observe(elapsed)
            if template != "/metrics":
                logger.info("request", extra={"extra_fields": {
                    "method": request.method, "route": template,
                    "status": status_code, "ms": round(elapsed * 1000, 1)}})

    app.include_router(ops.router)
    app.include_router(auth.router)
    app.include_router(clinical.router)
    return app


app = create_app()
