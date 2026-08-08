import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_summaries.providers import FakeProvider, GeminiProvider, ProviderFailure
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


@pytest.mark.parametrize(
    ("behavior", "code"),
    [
        ("timeout", "timeout"),
        ("rate_limited", "rate_limited"),
        ("unavailable", "unavailable"),
        ("malformed", "invalid_provider_output"),
    ],
)
def test_existing_fake_failure_behavior_is_preserved(behavior: str, code: str) -> None:
    with pytest.raises(ProviderFailure, match=code):
        FakeProvider(behavior).generate(
            SummaryInput(platform="github", canonical_hostname="github.com"),
            model="fake",
            prompt_version="ai-summary-v1",
            timeout_seconds=1,
        )


def test_disabled_unavailable_and_manual_generation_preserves_fields(
    client: TestClient, db_session: Session
) -> None:
    discovery_id = register_and_create(client)
    unavailable = client.get(f"/api/v1/discoveries/{discovery_id}/summary")
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "unavailable"
    assert unavailable.json()["availability_reason"] == "disabled"
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


def test_unavailable_reasons_distinguish_provider_and_metadata(
    client: TestClient, db_session: Session
) -> None:
    discovery_id = register_and_create(client, "availability@example.com")
    settings = get_settings()
    settings.ai_summaries_enabled = True
    settings.ai_summary_provider = "gemini"
    settings.ai_real_provider_enabled = False
    settings.gemini_api_key = None
    response = client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()
    assert response["availability_reason"] == "provider_unavailable"
    assert not response["can_generate"]

    settings.ai_summary_provider = "fake"
    response = client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()
    assert response["availability_reason"] == "insufficient_data"
    assert not response["can_generate"]

    discovery = db_session.scalar(select(Discovery))
    assert discovery is not None and discovery.metadata_record is not None
    discovery.metadata_record.title = "Approved public title"
    db_session.commit()
    response = client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()
    assert response["availability_reason"] is None
    assert response["can_generate"]


def test_expired_in_process_generation_becomes_retryable(
    client: TestClient, db_session: Session
) -> None:
    enable_fake()
    discovery_id = register_and_create(client, "interrupted@example.com")
    discovery = db_session.scalar(select(Discovery))
    assert discovery is not None
    row = AISummary(
        discovery_id=discovery.id,
        status="processing",
        last_attempted_at=datetime.now(UTC) - timedelta(minutes=2),
        processing_lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(row)
    db_session.commit()
    result = client.get(f"/api/v1/discoveries/{discovery_id}/summary").json()
    assert result["status"] == "failed"
    assert result["error"]["code"] == "unavailable"
    assert result["can_retry"]


def test_gemini_structured_output_uses_only_approved_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_client = MagicMock()
    sdk_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(
            {
                "summary": "A source-grounded summary.",
                "key_points": ["One supported point."],
                "topics": ["testing"],
                "entities": [],
                "language": "en",
                "confidence": 0.9,
                "insufficiency_reason": None,
            }
        ),
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=8),
    )
    monkeypatch.setattr(
        "app.ai_summaries.providers.genai.Client", MagicMock(return_value=sdk_client)
    )
    result = GeminiProvider("test-only-key").generate(
        SummaryInput(
            title="Approved title",
            description="Approved description",
            platform="github",
            canonical_hostname="github.com",
        ),
        model="gemini-3.6-flash",
        prompt_version="ai-summary-v1",
        timeout_seconds=1,
        max_output_tokens=321,
    )
    assert result.output.summary == "A source-grounded summary."
    call = sdk_client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-3.6-flash"
    assert call["config"].max_output_tokens == 321
    envelope = json.loads(call["contents"])
    assert envelope["source_data"]["title"] == "Approved title"
    serialized = call["contents"]
    for private_value in ["Private note", "Private reason", "raw_url", "user_id"]:
        assert private_value not in serialized


def test_gemini_rejects_malformed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk_client = MagicMock()
    sdk_client.models.generate_content.return_value = SimpleNamespace(
        text='{"summary":"missing required fields","raw_response":"must not persist"}',
        usage_metadata=None,
    )
    monkeypatch.setattr(
        "app.ai_summaries.providers.genai.Client", MagicMock(return_value=sdk_client)
    )
    with pytest.raises(ProviderFailure, match="invalid_provider_output"):
        GeminiProvider("test-only-key").generate(
            SummaryInput(platform="github", canonical_hostname="github.com"),
            model="gemini-3.6-flash",
            prompt_version="ai-summary-v1",
            timeout_seconds=1,
        )


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (httpx.ReadTimeout("late"), "timeout"),
        (type("RateLimit", (Exception,), {"code": 429})(), "rate_limited"),
        (type("Outage", (Exception,), {"code": 503})(), "unavailable"),
    ],
)
def test_gemini_classifies_safe_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    sdk_client = MagicMock()
    sdk_client.models.generate_content.side_effect = error
    monkeypatch.setattr(
        "app.ai_summaries.providers.genai.Client", MagicMock(return_value=sdk_client)
    )
    with pytest.raises(ProviderFailure, match=code):
        GeminiProvider("test-only-key").generate(
            SummaryInput(platform="github", canonical_hostname="github.com"),
            model="gemini-3.6-flash",
            prompt_version="ai-summary-v1",
            timeout_seconds=1,
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
