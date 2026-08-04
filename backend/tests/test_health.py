import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"service": "KeptIt API", "status": "ok"}


def test_health_check_does_not_require_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://invalid:invalid@127.0.0.1:1/missing")
    get_settings.cache_clear()

    try:
        response = client.get("/api/v1/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
