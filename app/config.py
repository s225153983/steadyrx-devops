"""Environment specific configuration.

Every setting is read from environment variables so the same Docker image can
run in the test, staging and production environments with different config
files (see deploy/config/*.env).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app import __version__


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings for one environment."""

    app_env: str = "development"
    app_version: str = __version__
    build_sha: str = "local"
    jwt_secret: str = "dev-only-secret-change-me-0123456789"
    jwt_ttl_minutes: int = 30
    database_path: str = ":memory:"
    seed_demo_data: bool = True
    log_level: str = "INFO"
    risk_threshold_high: float = 0.6
    risk_threshold_medium: float = 0.3
    allowed_origins: list[str] = field(default_factory=list)


def load_settings() -> Settings:
    """Build settings from the current process environment."""
    origins = os.getenv("ALLOWED_ORIGINS", "")
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_version=os.getenv("APP_VERSION", __version__),
        build_sha=os.getenv("BUILD_SHA", "local"),
        jwt_secret=os.getenv("JWT_SECRET", Settings.jwt_secret),
        jwt_ttl_minutes=int(os.getenv("JWT_TTL_MINUTES", "30")),
        database_path=os.getenv("DATABASE_PATH", ":memory:"),
        seed_demo_data=_bool(os.getenv("SEED_DEMO_DATA"), default=True),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        risk_threshold_high=float(os.getenv("RISK_THRESHOLD_HIGH", "0.6")),
        risk_threshold_medium=float(os.getenv("RISK_THRESHOLD_MEDIUM", "0.3")),
        allowed_origins=[o.strip() for o in origins.split(",") if o.strip()],
    )
