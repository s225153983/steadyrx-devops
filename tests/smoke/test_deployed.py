"""Post-deployment smoke tests.

Jenkins runs these against the live staging container (and again against
production after release). They are skipped in the unit test run because
BASE_URL is only set by the pipeline.
"""

import os

import httpx
import pytest

BASE_URL = os.getenv("BASE_URL")
EXPECTED_VERSION = os.getenv("EXPECTED_VERSION")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="BASE_URL not set")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        yield client


def test_service_is_live_and_ready(http):
    assert http.get("/health/live").status_code == 200
    assert http.get("/health/ready").json()["database"] is True


def test_deployed_version_matches_build(http):
    body = http.get("/version").json()
    if EXPECTED_VERSION:
        assert body["version"] == EXPECTED_VERSION


def test_login_and_risk_queue(http):
    res = http.post("/api/v1/auth/login",
                    json={"username": "daniel", "password": "Pharmacist!2026"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    queue = http.get("/api/v1/alerts",
                     headers={"Authorization": f"Bearer {token}"})
    assert queue.status_code == 200
    assert isinstance(queue.json(), list)


def test_metrics_are_exposed_for_prometheus(http):
    assert "steadyrx_http_requests_total" in http.get("/metrics").text
