"""Prometheus metrics exposed on /metrics."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

REQUESTS = Counter(
    "steadyrx_http_requests_total",
    "HTTP requests handled, labelled by route template and status code",
    ["method", "route", "status"],
)
LATENCY = Histogram(
    "steadyrx_http_request_duration_seconds",
    "HTTP request latency by route template",
    ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
ALERTS_CREATED = Counter(
    "steadyrx_alerts_created_total",
    "Falls-risk alerts raised by the gait engine",
    ["risk"],
)
OPEN_ALERTS = Gauge(
    "steadyrx_open_alerts",
    "Alerts waiting for pharmacist review",
    ["risk"],
)
LOGIN_FAILURES = Counter(
    "steadyrx_login_failures_total",
    "Failed login attempts, a signal of password guessing",
)
APP_INFO = Info("steadyrx_build", "Version and environment of the running build")
