import hashlib
import uuid
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discovery import Discovery


def register(client: TestClient, email: str = "owner@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
    )
    assert response.status_code == 201


def create(
    client: TestClient, url: str = "https://example.com/story", **fields: object
) -> Response:
    return cast(Response, client.post("/api/v1/discoveries", json={"url": url, **fields}))


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.instagram.com/p/abc", "instagram"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.tiktok.com/@person/video/1", "tiktok"),
        ("https://old.reddit.com/r/test/comments/1", "reddit"),
        ("https://twitter.com/person/status/1", "x"),
        ("https://www.github.com/org/repo", "github"),
        ("https://example.com/article", "generic_web"),
    ],
)
def test_creation_detects_platform(client: TestClient, url: str, platform: str) -> None:
    register(client)
    response = create(client, url, custom_title="  A title  ", personal_note=" Note ")
    assert response.status_code == 201
    assert response.json()["platform"] == platform
    assert response.json()["original_url"] == url
    assert response.json()["custom_title"] == "A title"


def test_creation_requires_authentication(client: TestClient) -> None:
    assert create(client).status_code == 401


def test_normalizes_and_hashes_url(client: TestClient, db_session: Session) -> None:
    register(client)
    original = "HTTPS://Example.COM:443/path?b=2&utm_source=news&a=1#part"
    response = create(client, original)
    assert response.status_code == 201
    assert response.json()["canonical_url"] == "https://example.com/path?a=1&b=2"
    record = db_session.scalar(select(Discovery))
    assert record is not None
    assert record.original_url == original
    assert record.canonical_url_hash == hashlib.sha256(record.canonical_url.encode()).digest()
    assert record.normalization_version == 1


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com/file",
        "https://user:pass@example.com/",
        "https://localhost/test",
        "http://127.0.0.1/test",
        "http://10.0.0.1/test",
        "https:///missing-host",
        "not a url",
    ],
)
def test_rejects_unsafe_or_malformed_urls(client: TestClient, url: str) -> None:
    register(client)
    response = create(client, url)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_url"


def test_duplicate_is_per_user_and_includes_archived(client: TestClient) -> None:
    register(client)
    first = create(client, "https://example.com/page?utm_campaign=x")
    client.post(f"/api/v1/discoveries/{first.json()['id']}/archive")
    duplicate = create(client, "https://EXAMPLE.com:443/page#section")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_discovery"

    client.post("/api/v1/auth/logout")
    register(client, "second@example.com")
    assert create(client, "https://example.com/page").status_code == 201


def test_list_search_filters_and_pagination(client: TestClient) -> None:
    register(client)
    one = create(client, "https://github.com/example/one", custom_title="Needle")
    create(client, "https://example.com/two", personal_note="needle note")
    three = create(client, "https://youtube.com/watch?v=three")
    client.patch(f"/api/v1/discoveries/{one.json()['id']}", json={"is_favourite": True})
    client.post(f"/api/v1/discoveries/{three.json()['id']}/archive")

    searched = client.get("/api/v1/discoveries", params={"q": "needle"}).json()
    assert searched["total"] == 2
    assert client.get("/api/v1/discoveries", params={"platform": "github"}).json()["total"] == 1
    assert client.get("/api/v1/discoveries", params={"favourite": True}).json()["total"] == 1
    assert client.get("/api/v1/discoveries", params={"archived": True}).json()["total"] == 1
    page = client.get("/api/v1/discoveries", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2
    assert len(page["results"]) == 1


def test_get_update_archive_restore_and_delete_are_owner_scoped(client: TestClient) -> None:
    register(client)
    created = create(client, "https://example.com/owned", save_reason="Read later").json()
    discovery_id = created["id"]
    updated = client.patch(
        f"/api/v1/discoveries/{discovery_id}",
        json={
            "custom_title": "Updated",
            "personal_note": "Note",
            "save_reason": None,
            "is_favourite": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["is_favourite"] is True
    assert (
        client.patch(
            f"/api/v1/discoveries/{discovery_id}", json={"original_url": "https://evil.test"}
        ).status_code
        == 422
    )
    assert (
        client.post(f"/api/v1/discoveries/{discovery_id}/archive").json()["archived_at"] is not None
    )
    assert client.post(f"/api/v1/discoveries/{discovery_id}/archive").status_code == 200
    assert client.post(f"/api/v1/discoveries/{discovery_id}/restore").json()["archived_at"] is None

    client.post("/api/v1/auth/logout")
    register(client, "intruder@example.com")
    for method, suffix in [("get", ""), ("patch", ""), ("post", "/archive"), ("delete", "")]:
        request = getattr(client, method)
        kwargs = {"json": {"custom_title": "No"}} if method == "patch" else {}
        assert request(f"/api/v1/discoveries/{discovery_id}{suffix}", **kwargs).status_code == 404

    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "long-enough-password"},
    )
    assert client.delete(f"/api/v1/discoveries/{discovery_id}").status_code == 204
    assert client.get(f"/api/v1/discoveries/{discovery_id}").status_code == 404


def test_library_never_returns_another_users_discovery(client: TestClient) -> None:
    register(client)
    create(client, "https://example.com/private")
    client.post("/api/v1/auth/logout")
    register(client, "other@example.com")
    assert client.get("/api/v1/discoveries").json()["results"] == []


def test_state_changes_reject_untrusted_origin(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/discoveries",
        json={"url": "https://example.com"},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403


def test_uuid_is_version_four(client: TestClient) -> None:
    register(client)
    discovery_id = uuid.UUID(create(client).json()["id"])
    assert discovery_id.version == 4
