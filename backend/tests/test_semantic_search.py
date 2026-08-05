import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.discovery import Discovery
from app.models.discovery_embedding import DiscoveryEmbedding
from app.semantic_search.document import build_document
from app.semantic_search.providers import (
    EmbeddingProviderError,
    FakeEmbeddingProvider,
    GeminiEmbeddingProvider,
    _classify_gemini_error,
    get_provider,
)
from app.semantic_search.schemas import SemanticSearchRequest
from app.semantic_search.service import build_postgresql_semantic_statement


def create_discovery(client: TestClient, email: str = "semantic@example.com") -> str:
    assert (
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/discoveries",
        json={
            "url": "https://example.com/railway",
            "custom_title": "Abandoned railway town",
            "personal_note": "private note",
            "save_reason": "private reason",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def enable_fake() -> None:
    settings = get_settings()
    settings.semantic_search_enabled = True
    settings.embedding_provider = "fake"
    settings.embedding_fake_behavior = "success"


def test_fake_provider_is_deterministic_and_rejects_bad_dimension() -> None:
    provider = FakeEmbeddingProvider("fake", 1536)
    assert (
        provider.embed_one("日本の廃線", "query", 1).vector
        == provider.embed_one("日本の廃線", "query", 1).vector
    )
    assert len(provider.embed_one("text", "document", 1).vector) == 1536
    malformed = FakeEmbeddingProvider("fake", 1536, "malformed_dimension")
    try:
        malformed.embed_one("text", "document", 1)
    except EmbeddingProviderError as exc:
        assert exc.code == "invalid_output"
    else:
        raise AssertionError("malformed dimensions must fail")


def gemini_settings(
    *, embedding_real_provider_enabled: bool = True, gemini_api_key: str | None = "test-only-key"
) -> Settings:
    settings = Settings(_env_file=None)
    settings.embedding_provider = "gemini"
    settings.embedding_model = "gemini-embedding-001"
    settings.embedding_dimension = 1536
    settings.embedding_real_provider_enabled = embedding_real_provider_enabled
    settings.gemini_api_key = gemini_api_key
    return settings


def test_gemini_provider_requests_model_dimension_and_task_types(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = MagicMock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.25] * 1536)], metadata=None
    )
    client_factory = MagicMock(return_value=client)
    monkeypatch.setattr("app.semantic_search.providers.genai.Client", client_factory)
    provider = get_provider(gemini_settings())

    document = provider.embed_one("approved document", "document", 2.5)
    provider.embed_one("private query", "query", 2.5)

    assert len(document.vector) == 1536
    assert document.usage_tokens is None
    assert client_factory.call_args.kwargs == {"api_key": "test-only-key"}
    first, second = client.models.embed_content.call_args_list
    assert first.kwargs["model"] == "gemini-embedding-001"
    assert first.kwargs["config"].output_dimensionality == 1536
    assert first.kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert second.kwargs["config"].task_type == "RETRIEVAL_QUERY"
    assert "approved document" not in caplog.text
    assert "private query" not in caplog.text
    assert "test-only-key" not in caplog.text
    assert "[0.25" not in caplog.text


def test_gemini_provider_rejects_malformed_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    monkeypatch.setattr(
        "app.semantic_search.providers.genai.Client", MagicMock(return_value=client)
    )
    provider = GeminiEmbeddingProvider(gemini_settings())
    invalid = [[], [0.2] * 1535, [float("nan")] * 1536, [float("inf")] * 1536]
    for values in invalid:
        client.models.embed_content.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=values)] if values else [], metadata=None
        )
        try:
            provider.embed_one("private input", "query", 1)
        except EmbeddingProviderError as exc:
            assert exc.code == "invalid_output"
        else:
            raise AssertionError("malformed Gemini output must fail")


def test_gemini_configuration_is_lazy_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    assert gemini_settings(gemini_api_key=None)
    for settings in (
        gemini_settings(embedding_real_provider_enabled=False),
        gemini_settings(gemini_api_key=None),
    ):
        try:
            get_provider(settings)
        except EmbeddingProviderError as exc:
            assert exc.code == "not_configured"
        else:
            raise AssertionError("unconfigured Gemini provider must be unavailable")
    monkeypatch.setattr("app.semantic_search.providers.genai.Client", MagicMock())


def test_health_works_with_gemini_selected_without_key(client: TestClient) -> None:
    settings = get_settings()
    settings.embedding_provider = "gemini"
    settings.embedding_model = "gemini-embedding-001"
    settings.gemini_api_key = None

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_gemini_error_classification_is_safe() -> None:
    class ProviderFailure(Exception):
        def __init__(self, code: int) -> None:
            self.code = code

    expected = {
        401: "invalid_credentials",
        403: "permission_denied",
        429: "rate_limited",
        503: "unavailable",
    }
    for status_code, expected_code in expected.items():
        classified = _classify_gemini_error(ProviderFailure(status_code))
        assert classified.code == expected_code
        assert str(classified) == "The embedding provider is temporarily unavailable."
    assert _classify_gemini_error(httpx.TimeoutException("private payload")).code == "timeout"
    assert _classify_gemini_error(httpx.ConnectError("private payload")).code == "network_failure"


def test_document_policy_and_staleness(client: TestClient, db_session: Session) -> None:
    enable_fake()
    discovery_id = create_discovery(client)
    discovery = db_session.get(Discovery, uuid.UUID(discovery_id))
    assert discovery is not None
    document = build_document(discovery)
    assert "Abandoned railway town" in document.text
    assert "private note" not in document.text
    assert "private reason" not in document.text
    response = client.post(
        f"/api/v1/discoveries/{discovery_id}/embedding",
        json={},
        headers={"Idempotency-Key": "semantic-index-0001"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "succeeded"
    assert "embedding" not in response.text
    discovery.personal_note = "changed private note"
    db_session.commit()
    assert (
        client.get(f"/api/v1/discoveries/{discovery_id}/embedding/status").json()["status"]
        == "succeeded"
    )
    discovery.custom_title = "Changed searchable title"
    db_session.commit()
    assert (
        client.get(f"/api/v1/discoveries/{discovery_id}/embedding/status").json()["status"]
        == "stale"
    )


def test_switching_fake_to_gemini_is_stale_and_reindex_replaces_row(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_fake()
    discovery_id = create_discovery(client, "provider-switch@example.com")
    response = client.post(
        f"/api/v1/discoveries/{discovery_id}/embedding",
        json={},
        headers={"Idempotency-Key": "provider-switch-fake"},
    )
    assert response.status_code == 202
    settings = get_settings()
    settings.embedding_provider = "gemini"
    settings.embedding_model = "gemini-embedding-001"
    settings.embedding_real_provider_enabled = True
    settings.gemini_api_key = "test-only-key"
    assert (
        client.get(f"/api/v1/discoveries/{discovery_id}/embedding/status").json()["status"]
        == "stale"
    )

    sdk_client = MagicMock()
    sdk_client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.5] * 1536)], metadata=None
    )
    monkeypatch.setattr(
        "app.semantic_search.providers.genai.Client", MagicMock(return_value=sdk_client)
    )
    response = client.post(
        f"/api/v1/discoveries/{discovery_id}/embedding/retry",
        json={"confirm": True},
        headers={"Idempotency-Key": "provider-switch-gemini"},
    )
    assert response.status_code == 202
    row = db_session.scalar(select(DiscoveryEmbedding))
    assert row is not None
    assert (row.provider, row.model, row.embedding_dimension) == (
        "gemini",
        "gemini-embedding-001",
        1536,
    )
    assert row.status == "succeeded"
    assert row.usage_tokens is None


def test_owner_isolation_and_hybrid_fallback(client: TestClient, db_session: Session) -> None:
    enable_fake()
    discovery_id = create_discovery(client)
    assert db_session.scalar(select(DiscoveryEmbedding)) is None
    result = client.post(
        "/api/v1/search/semantic", json={"query": "Abandoned railway", "mode": "hybrid"}
    )
    assert result.status_code == 200
    assert result.json()["search"]["fallback_reason"] == "no_current_embeddings"
    client.post("/api/v1/auth/logout")
    create_discovery(client, "other-semantic@example.com")
    assert client.get(f"/api/v1/discoveries/{discovery_id}/embedding/status").status_code == 404


def test_postgresql_pgvector_query_is_owner_scoped_and_filtered() -> None:
    db = MagicMock(spec=Session)
    db.scalar.return_value = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = SemanticSearchRequest.model_validate(
        {
            "query": "remembered meaning",
            "filters": {
                "platform": ["youtube", "github"],
                "tag_id": str(uuid.uuid4()),
                "space_id": str(uuid.uuid4()),
                "is_favourite": True,
                "archive": "archived",
            },
        }
    )
    settings = get_settings()
    statement = build_postgresql_semantic_statement(
        db, user_id, payload, settings, [0.01] * settings.embedding_dimension
    )
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": False},
        )
    )
    assert "<=>" in compiled
    assert "discoveries.user_id" in compiled
    assert "discovery_tags" in compiled
    assert "space_memberships" in compiled
    assert "discoveries.platform IN" in compiled
    assert "discoveries.is_favourite" in compiled
    assert "discoveries.archived_at IS NOT NULL" in compiled
    assert "discovery_embeddings.status" in compiled
    assert "discovery_embeddings.provider" in compiled
    assert "discovery_embeddings.model" in compiled
    assert "discovery_embeddings.embedding_dimension" in compiled
    assert "LIMIT" in compiled
