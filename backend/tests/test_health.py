import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"service": "KeptIt API", "status": "ok"}


def test_health_check_does_not_require_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://invalid:invalid@127.0.0.1:1/missing")
    get_settings.cache_clear()

    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/api/v1/readiness")

    assert response.status_code == 200
    assert response.json() == {"service": "KeptIt API", "status": "ok"}


def test_readiness_returns_safe_503_for_database_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_execute(*_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("secret-db-host.example"))

    monkeypatch.setattr(db_session, "execute", fail_execute)
    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    assert response.json() == {"service": "KeptIt API", "status": "unavailable"}
    assert "secret-db-host" not in response.text
