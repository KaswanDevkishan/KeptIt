import uuid
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.discovery import Discovery
from app.models.tag import DiscoveryTag
from app.models.tag import Tag as TagModel
from app.models.user import User


def register(client: TestClient, email: str = "tag-owner@example.com") -> None:
    assert (
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
        ).status_code
        == 201
    )


def discovery(client: TestClient, suffix: str = "one") -> str:
    response = client.post("/api/v1/discoveries", json={"url": f"https://example.com/{suffix}"})
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def tag(client: TestClient, name: str = "Python") -> dict[str, object]:
    response = client.post("/api/v1/tags", json={"name": name})
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_tag_crud_normalization_search_and_auth(client: TestClient) -> None:
    assert client.post("/api/v1/tags", json={"name": "Python"}).status_code == 401
    register(client)
    created = tag(client, "  Ｐｙｔｈｏｎ  ")
    assert created["name"] == "Ｐｙｔｈｏｎ"
    for equivalent in ("Python", "python", " python "):
        response = client.post("/api/v1/tags", json={"name": equivalent})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "tag_name_conflict"
    for invalid in ("", "   ", "bad\0name", "bad\nname", "x" * 51):
        assert client.post("/api/v1/tags", json={"name": invalid}).status_code == 422
    second = tag(client, "Accessibility")
    listed = client.get("/api/v1/tags", params={"q": "THO"}).json()
    assert [item["id"] for item in listed["items"]] == [created["id"]]
    assert [item["name"] for item in client.get("/api/v1/tags").json()["items"]] == [
        "Accessibility",
        "Ｐｙｔｈｏｎ",
    ]
    renamed = client.patch(f"/api/v1/tags/{second['id']}", json={"name": "A11y"})
    assert renamed.status_code == 200
    assert client.delete(f"/api/v1/tags/{second['id']}").status_code == 204


def test_memberships_summaries_filter_limits_and_cascades(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    discovery_id = discovery(client)
    first, second = tag(client, "Python"), tag(client, "Web")
    path = f"/api/v1/tags/{first['id']}/discoveries/{discovery_id}"
    created = client.put(path)
    assert created.status_code == 201
    assert client.put(path).status_code == 200
    assert client.put(f"/api/v1/tags/{second['id']}/discoveries/{discovery_id}").status_code == 201
    payload = client.get(f"/api/v1/discoveries/{discovery_id}").json()
    assert [item["name"] for item in payload["tags"]] == ["Python", "Web"]
    assert client.get("/api/v1/discoveries", params={"tag_id": first["id"]}).json()["total"] == 1
    assert (
        client.get(f"/api/v1/tags/{first['id']}/discoveries").json()["items"][0]["id"]
        == discovery_id
    )
    assert client.delete(f"/api/v1/tags/{first['id']}").status_code == 204
    assert db_session.get(Discovery, uuid.UUID(discovery_id)) is not None
    assert db_session.scalar(select(func.count()).select_from(DiscoveryTag)) == 1
    assert (
        client.delete(f"/api/v1/tags/{second['id']}/discoveries/{discovery_id}").status_code == 204
    )


def test_owner_isolation_and_foreign_missing_match(client: TestClient) -> None:
    register(client)
    owned_tag, owned_discovery = tag(client), discovery(client)
    client.post("/api/v1/auth/logout")
    register(client, "other-tag-owner@example.com")
    other_tag, other_discovery = tag(client), discovery(client, "other")
    missing = uuid.uuid4()
    foreign = client.get(f"/api/v1/tags/{owned_tag['id']}")
    absent = client.get(f"/api/v1/tags/{missing}")
    assert (foreign.status_code, foreign.json()) == (absent.status_code, absent.json())
    assert (
        client.put(f"/api/v1/tags/{other_tag['id']}/discoveries/{owned_discovery}").status_code
        == 404
    )
    assert (
        client.put(f"/api/v1/tags/{owned_tag['id']}/discoveries/{other_discovery}").status_code
        == 404
    )


def test_twenty_tag_limit(client: TestClient) -> None:
    register(client)
    discovery_id = discovery(client)
    for index in range(20):
        created = tag(client, f"Tag {index}")
        assert (
            client.put(f"/api/v1/tags/{created['id']}/discoveries/{discovery_id}").status_code
            == 201
        )
    overflow = tag(client, "Overflow")
    response = client.put(f"/api/v1/tags/{overflow['id']}/discoveries/{discovery_id}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "discovery_tag_limit_reached"


def test_five_hundred_tag_limit(client: TestClient, db_session: Session) -> None:
    register(client)
    user_id = db_session.scalar(select(User.id))
    assert user_id is not None
    db_session.add_all(
        TagModel(user_id=user_id, name=f"Tag {index}", normalized_name=f"tag {index}")
        for index in range(500)
    )
    db_session.commit()
    response = client.post("/api/v1/tags", json={"name": "Overflow"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tag_limit_reached"


def test_tag_filter_combines_with_space_keyword_platform_favourite_and_archive(
    client: TestClient,
) -> None:
    register(client)
    discovery_id = discovery(client, "combined-python")
    created_tag = tag(client)
    created_space = client.post("/api/v1/spaces", json={"name": "Learning"}).json()
    client.put(f"/api/v1/tags/{created_tag['id']}/discoveries/{discovery_id}")
    client.put(f"/api/v1/spaces/{created_space['id']}/discoveries/{discovery_id}")
    client.patch(
        f"/api/v1/discoveries/{discovery_id}",
        json={"is_favourite": True, "custom_title": "Python guide"},
    )
    params = {
        "tag_id": created_tag["id"],
        "space_id": created_space["id"],
        "q": "guide",
        "platform": "generic_web",
        "favourite": True,
    }
    assert client.get("/api/v1/discoveries", params=params).json()["total"] == 1
    client.post(f"/api/v1/discoveries/{discovery_id}/archive")
    assert client.get("/api/v1/discoveries", params=params).json()["total"] == 0
    assert (
        client.get("/api/v1/discoveries", params={**params, "archived": True}).json()["total"] == 1
    )
