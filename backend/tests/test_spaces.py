import uuid
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.discovery import Discovery
from app.models.space import Space, SpaceMembership


def register(client: TestClient, email: str = "space-owner@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
    )
    assert response.status_code == 201


def create_discovery(client: TestClient, suffix: str = "one") -> str:
    response = client.post("/api/v1/discoveries", json={"url": f"https://example.com/{suffix}"})
    assert response.status_code == 201
    return str(response.json()["id"])


def create_space(client: TestClient, name: str = "Recipes") -> dict[str, object]:
    response = client.post("/api/v1/spaces", json={"name": name})
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_space_creation_list_validation_and_duplicate_normalization(client: TestClient) -> None:
    assert client.get("/api/v1/spaces").status_code == 401
    register(client)
    created = client.post(
        "/api/v1/spaces", json={"name": "  Ｒecipes  ", "description": "  Dinner ideas  "}
    )
    assert created.status_code == 201
    assert created.headers["location"].endswith(created.json()["id"])
    assert created.json()["name"] == "Ｒecipes"
    assert created.json()["description"] == "Dinner ideas"
    assert created.json()["discovery_count"] == 0
    duplicate = client.post("/api/v1/spaces", json={"name": "recipes"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "space_name_conflict"
    assert client.post("/api/v1/spaces", json={"name": "   "}).status_code == 422
    assert client.post("/api/v1/spaces", json={"name": "bad\u0000name"}).status_code == 422
    assert client.post("/api/v1/spaces", json={"name": "bad\nname"}).status_code == 422
    assert client.post("/api/v1/spaces", json={"name": "x", "unknown": True}).status_code == 422
    listed = client.get("/api/v1/spaces", params={"sort": "name_asc"}).json()
    assert [space["id"] for space in listed["items"]] == [created.json()["id"]]


def test_rename_noop_description_clear_conflict_and_delete(client: TestClient) -> None:
    register(client)
    first = create_space(client, "First")
    second = create_space(client, "Second")
    unchanged = client.patch(f"/api/v1/spaces/{first['id']}", json={"name": "First"})
    assert unchanged.status_code == 200
    assert unchanged.json()["updated_at"] == first["updated_at"]
    renamed = client.patch(
        f"/api/v1/spaces/{first['id']}", json={"name": "Renamed", "description": "Note"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"
    assert (
        client.patch(f"/api/v1/spaces/{first['id']}", json={"description": None}).json()[
            "description"
        ]
        is None
    )
    conflict = client.patch(f"/api/v1/spaces/{first['id']}", json={"name": "SECOND"})
    assert conflict.status_code == 409
    assert client.get(f"/api/v1/spaces/{second['id']}").status_code == 200
    assert client.patch(f"/api/v1/spaces/{first['id']}", json={}).status_code == 422
    assert client.delete(f"/api/v1/spaces/{first['id']}").status_code == 204
    assert client.get(f"/api/v1/spaces/{first['id']}").status_code == 404


def test_membership_add_is_idempotent_multiple_spaces_filter_and_remove(
    client: TestClient,
) -> None:
    register(client)
    discovery_id = create_discovery(client)
    first = create_space(client, "First")
    second = create_space(client, "Second")
    path = f"/api/v1/spaces/{first['id']}/discoveries/{discovery_id}"
    added = client.put(path)
    assert added.status_code == 201
    repeated = client.put(path)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == added.json()["id"]
    assert repeated.json()["created_at"] == added.json()["created_at"]
    assert (
        client.post(f"/api/v1/spaces/{second['id']}/discoveries/{discovery_id}").status_code == 201
    )
    assert client.get(f"/api/v1/spaces/{first['id']}").json()["discovery_count"] == 1
    contents = client.get(f"/api/v1/spaces/{first['id']}/discoveries").json()
    assert [item["id"] for item in contents["items"]] == [discovery_id]
    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 404


def test_archived_membership_and_space_delete_preserve_discovery(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    discovery_id = create_discovery(client)
    space = create_space(client)
    client.put(f"/api/v1/spaces/{space['id']}/discoveries/{discovery_id}")
    client.post(f"/api/v1/discoveries/{discovery_id}/archive")
    base = f"/api/v1/spaces/{space['id']}/discoveries"
    assert client.get(base).json()["items"] == []
    assert len(client.get(base, params={"archive": "archived"}).json()["items"]) == 1
    assert len(client.get(base, params={"archive": "all"}).json()["items"]) == 1
    assert client.delete(f"/api/v1/spaces/{space['id']}").status_code == 204
    assert db_session.get(Discovery, uuid.UUID(discovery_id)) is not None
    assert db_session.scalar(select(func.count()).select_from(SpaceMembership)) == 0


def test_ownership_isolation_and_foreign_missing_are_indistinguishable(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    owner_space = create_space(client, "Private")
    owner_discovery = create_discovery(client, "private")
    client.post("/api/v1/auth/logout")
    register(client, "other-space-owner@example.com")
    other_space = create_space(client, "Private")
    other_discovery = create_discovery(client, "other")
    missing = uuid.uuid4()
    foreign = client.get(f"/api/v1/spaces/{owner_space['id']}")
    absent = client.get(f"/api/v1/spaces/{missing}")
    assert (foreign.status_code, foreign.json()) == (absent.status_code, absent.json())
    assert (
        client.put(f"/api/v1/spaces/{other_space['id']}/discoveries/{owner_discovery}").status_code
        == 404
    )
    assert (
        client.put(f"/api/v1/spaces/{owner_space['id']}/discoveries/{other_discovery}").status_code
        == 404
    )
    assert client.get("/api/v1/spaces").json()["items"][0]["id"] == other_space["id"]
    assert db_session.scalar(select(func.count()).select_from(Space)) == 2


def test_mutations_require_trusted_origin_and_uuid_validation(client: TestClient) -> None:
    register(client)
    assert (
        client.post(
            "/api/v1/spaces",
            json={"name": "Nope"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/spaces/not-a-uuid").status_code == 422
