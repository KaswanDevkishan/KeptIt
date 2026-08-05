import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.discovery import Discovery
from app.models.discovery_embedding import DiscoveryEmbedding
from app.semantic_search.document import build_document
from app.semantic_search.providers import EmbeddingProviderError, FakeEmbeddingProvider
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
