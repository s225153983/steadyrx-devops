"""Unit tests for environment specific configuration."""

from app.config import load_settings


def test_defaults(monkeypatch):
    for key in ("APP_ENV", "SEED_DEMO_DATA", "ALLOWED_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings()
    assert settings.app_env == "development"
    assert settings.seed_demo_data is True
    assert settings.allowed_origins == []


def test_production_values_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SEED_DEMO_DATA", "false")
    monkeypatch.setenv("RISK_THRESHOLD_HIGH", "0.7")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
    settings = load_settings()
    assert settings.app_env == "production"
    assert settings.seed_demo_data is False
    assert settings.risk_threshold_high == 0.7
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]
