import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_summaries.providers import FakeProvider
from app.ai_summaries.schemas import SummaryInput
from app.ai_summaries.service import fingerprint
from app.core.config import get_settings
from app.models.ai_summary import AISummary
from app.models.discovery import Discovery


def register_and_create(client: TestClient, email: str = "summary@example.com") -> str:
    assert (
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/discoveries",
        json={
            "url": "https://example.com/article",
            "custom_title": "Private title",
            "personal_note": "Private note",
            "save_reason": "Private reason",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def enable_fake() -> None:
    settings = get_settings()
    settings.ai_summaries_enabled = True
    settings.ai_summary_provider = "fake"
    settings.ai_summary_fake_behavior = "success"
    settings.ai_summary_regeneration_cooldown_seconds = 0


def test_fake_is_deterministic_and_fingerprint_uses_only_approved_input() -> None:
    data = SummaryInput(
        title="A title",
        description="A description",
        platform="generic_web",
        canonical_hostname="example.com",
    )
    provider = FakeProvider()
    first = provider.generate(data, model="fake", prompt_version="ai-summary-v1", timeout_seconds=1)
    second = provider.generate(
        data, model="fake", prompt_version="ai-summary-v1", timeout_seconds=1
    )
    assert first == second
    assert fingerprint(data) == fingerprint(data)
    assert len(fingerprint(data)) == hashlib.sha256().digest_size


def test_disabled_unavailable_and_manual_generation_preserves_fields(
    client: TestClient, db_session: Session
) -> None:
    discovery_id = register_and_create(client)
    unavailable = client.get(f"/api/v1/discoveries/{discovery_id}/summary")
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "unavailable"
    assert (
        client.post(
            f"/api/v1/discoveries/{discovery_id}/summary",
            json={},
            headers={"Idempotency-Key": "disabled-request-001"},
        ).status_code
        == 503
    )
    assert db_session.scalar(select(AISummary)) is None
    enable_fake()
    discovery = db_session.scalar(select(Discovery))
    assert discovery is not None
    assert discovery.metadata_record is not None
    discovery.metadata_record.title = "Public source title"
    discovery.metadata_record.description = "Public source description"
    discovery.metadata_record.status = "succeeded"
    db_session.commit()
    accepted = client.post(
        f"/api/v1/discoveries/{discovery_id}/summary",
        json={},
        headers={"Idempotency-Key": "generation-request-001"},
    )
    assert accepted.status_code == 202
    result = client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()
    assert result["status"] == "succeeded"
    db_session.refresh(discovery)
    assert (discovery.custom_title, discovery.personal_note, discovery.save_reason) == (
        "Private title",
        "Private note",
        "Private reason",
    )


def test_stale_ignores_user_fields_and_delete_is_owner_scoped(
    client: TestClient, db_session: Session
) -> None:
    enable_fake()
    discovery_id = register_and_create(client)
    discovery = db_session.scalar(select(Discovery))
    assert discovery is not None
    assert discovery.metadata_record is not None
    discovery.metadata_record.title = "Source title"
    discovery.metadata_record.description = "Description"
    discovery.metadata_record.status = "succeeded"
    db_session.commit()
    client.post(
        f"/api/v1/discoveries/{discovery_id}/summary",
        json={},
        headers={"Idempotency-Key": "generation-request-002"},
    )
    client.patch(
        f"/api/v1/discoveries/{discovery_id}",
        json={"custom_title": "Changed", "personal_note": "Changed note"},
    )
    assert client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()["status"] == "succeeded"
    discovery.metadata_record.title = "Changed metadata"
    db_session.commit()
    assert client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()["status"] == "stale"
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "long-enough-password"},
    )
    assert client.get(f"/api/v1/discoveries/{discovery_id}/summary").status_code == 404
    assert client.delete(f"/api/v1/discoveries/{discovery_id}/summary").status_code == 404
