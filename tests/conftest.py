"""Shared fixtures. Each test gets a fresh app with its own database."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_SECRET = "test-secret-key-that-is-long-enough-123"


@pytest.fixture
def settings():
    return Settings(app_env="test", jwt_secret=TEST_SECRET,
                    database_path=":memory:", seed_demo_data=True)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _login(client, username, password):
    res = client.post("/api/v1/auth/login",
                      json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def pharmacist(client):
    return _login(client, "daniel", "Pharmacist!2026")


@pytest.fixture
def carer(client):
    return _login(client, "priya", "Carer!2026")
