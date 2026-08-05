import socket

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.metadata import fetcher
from app.metadata import providers as metadata_providers
from app.metadata.fetcher import FetchError, validate_public_url
from app.metadata.parser import ParsedMetadata, parse_html
from app.metadata.providers import ProviderResult
from app.models.discovery import Discovery, MetadataRecord


def register(client: TestClient, email: str = "metadata@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "long-enough-password"}
    )
    assert response.status_code == 201


def test_create_adds_pending_metadata_without_changing_user_fields(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    response = client.post(
        "/api/v1/discoveries",
        json={
            "url": "https://example.com/article",
            "custom_title": "My title",
            "personal_note": "My private note",
        },
    )
    assert response.status_code == 201
    assert response.json()["metadata"]["status"] == "pending"
    discovery = db_session.scalar(select(Discovery))
    record = db_session.scalar(select(MetadataRecord))
    assert discovery is not None and record is not None
    assert discovery.custom_title == "My title"
    assert discovery.personal_note == "My private note"
    assert record.discovery_id == discovery.id


def test_unsupported_platform_retry_is_safe_and_idempotent(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    created = client.post(
        "/api/v1/discoveries", json={"url": "https://www.instagram.com/p/example"}
    ).json()
    first = client.post(f"/api/v1/discoveries/{created['id']}/enrich")
    second = client.post(f"/api/v1/discoveries/{created['id']}/enrich/retry")
    assert first.status_code == second.status_code == 200
    assert second.json()["metadata"]["status"] == "unsupported"
    assert second.json()["metadata"]["failure_code"] == "platform_unsupported"
    assert len(list(db_session.scalars(select(MetadataRecord)))) == 1


def test_missing_youtube_configuration_does_not_fail_creation(client: TestClient) -> None:
    register(client)
    created = client.post(
        "/api/v1/discoveries", json={"url": "https://www.youtube.com/watch?v=public"}
    )
    assert created.status_code == 201
    enriched = client.post(f"/api/v1/discoveries/{created.json()['id']}/enrich")
    assert enriched.status_code == 200
    assert enriched.json()["metadata"]["status"] == "unsupported"
    assert enriched.json()["metadata"]["failure_code"] == "provider_not_configured"


def test_fetched_title_never_overwrites_custom_title(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    created = client.post(
        "/api/v1/discoveries",
        json={"url": "https://example.com/title", "custom_title": "User title"},
    )
    monkeypatch.setattr(
        metadata_providers,
        "generic",
        lambda _url, _settings: ProviderResult(
            "generic_html", ParsedMetadata(title="Fetched title")
        ),
    )
    enriched = client.post(f"/api/v1/discoveries/{created.json()['id']}/enrich")
    assert enriched.json()["custom_title"] == "User title"
    assert enriched.json()["metadata"]["title"] == "Fetched title"
    assert enriched.json()["display_title"] == "User title"


def test_github_rate_limit_is_stored_as_safe_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    created = client.post("/api/v1/discoveries", json={"url": "https://github.com/example/project"})

    def rate_limited(_url: str, _settings: Settings) -> ProviderResult:
        raise FetchError("rate_limited", "GitHub metadata is temporarily rate limited.")

    monkeypatch.setattr(metadata_providers, "github", rate_limited)
    enriched = client.post(f"/api/v1/discoveries/{created.json()['id']}/enrich")
    assert enriched.json()["metadata"]["status"] == "failed"
    assert enriched.json()["metadata"]["failure_code"] == "rate_limited"


def test_another_users_enrichment_is_not_found(client: TestClient) -> None:
    register(client)
    discovery_id = client.post(
        "/api/v1/discoveries", json={"url": "https://example.com/private"}
    ).json()["id"]
    client.post("/api/v1/auth/logout")
    register(client, "other-metadata@example.com")
    assert client.post(f"/api/v1/discoveries/{discovery_id}/enrich").status_code == 404


def test_metadata_cascades_when_discovery_is_deleted(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    discovery_id = client.post(
        "/api/v1/discoveries", json={"url": "https://example.com/delete"}
    ).json()["id"]
    assert client.delete(f"/api/v1/discoveries/{discovery_id}").status_code == 204
    assert db_session.scalar(select(MetadataRecord)) is None


def test_html_parser_prioritizes_open_graph_and_bounds_fields() -> None:
    body = b"""
        <html><head><title>Fallback title</title>
        <meta name="description" content="Fallback description">
        <meta property="og:title" content="  Open   Graph title  ">
        <meta property="og:description" content="Preferred description">
        <meta property="og:image" content="/preview.jpg">
        <meta name="author" content="Publisher">
        </head></html>
    """
    parsed = parse_html(body, "https://example.com/articles/one")
    assert parsed.title == "Open Graph title"
    assert parsed.description == "Preferred description"
    assert parsed.thumbnail_url == "https://example.com/preview.jpg"
    assert parsed.creator_or_publisher == "Publisher"
    assert parse_html(b"<title>" + b"x" * 900 + b"</title>", "https://example.com").title == (
        "x" * 500
    )
    assert parse_html(b"<title>broken", "https://example.com").title == "broken"


@pytest.mark.parametrize(
    ("address", "url"),
    [
        ("127.0.0.1", "http://example.test"),
        ("10.0.0.4", "https://example.test"),
        ("169.254.1.1", "https://example.test"),
    ],
)
def test_fetch_validation_rejects_non_public_addresses(
    monkeypatch: pytest.MonkeyPatch, address: str, url: str
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(FetchError) as caught:
        validate_public_url(url)
    assert caught.value.code == "unsafe_host"


def test_fetch_validation_rejects_credentials_and_allows_public_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(FetchError, match="credentials"):
        validate_public_url("https://user:secret@example.com")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    validate_public_url("https://example.com/path")


class _FakeResponse:
    def __init__(
        self,
        url: str,
        *,
        status: int = 200,
        content_type: str = "text/html",
        chunks: list[bytes] | None = None,
        location: str | None = None,
    ) -> None:
        self.url = url
        self.status_code = status
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location
        self.chunks = chunks or [b"<title>Safe</title>"]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def iter_bytes(self) -> list[bytes]:
        return self.chunks


class _FakeClient:
    responses: list[_FakeResponse | Exception] = []

    def __init__(self, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def stream(self, *_args: object) -> _FakeResponse:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _mock_fetch(
    monkeypatch: pytest.MonkeyPatch, responses: list[_FakeResponse | Exception]
) -> None:
    _FakeClient.responses = responses
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    monkeypatch.setattr(fetcher, "validate_public_url", lambda _url: None)


def test_fetch_enforces_size_type_timeout_and_redirect_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(metadata_max_response_bytes=16_384, metadata_max_redirects=1)
    _mock_fetch(
        monkeypatch,
        [_FakeResponse("https://public.example", chunks=[b"x" * 16_385])],
    )
    with pytest.raises(FetchError) as too_large:
        fetcher.fetch("https://public.example", settings)
    assert too_large.value.code == "response_too_large"

    _mock_fetch(
        monkeypatch,
        [_FakeResponse("https://public.example", content_type="video/mp4")],
    )
    with pytest.raises(FetchError) as wrong_type:
        fetcher.fetch("https://public.example", settings)
    assert wrong_type.value.code == "unsupported_content_type"

    _mock_fetch(monkeypatch, [httpx.ReadTimeout("timed out")])
    with pytest.raises(FetchError) as timed_out:
        fetcher.fetch("https://public.example", settings)
    assert timed_out.value.code == "timeout"

    _mock_fetch(
        monkeypatch,
        [
            _FakeResponse("https://one.example", status=302, location="https://two.example"),
            _FakeResponse("https://two.example", status=302, location="https://three.example"),
        ],
    )
    with pytest.raises(FetchError) as redirects:
        fetcher.fetch("https://one.example", settings)
    assert redirects.value.code == "too_many_redirects"


def test_fetch_accepts_safe_redirect_and_revalidates_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[str] = []
    _FakeClient.responses = [
        _FakeResponse("https://one.example", status=302, location="/final"),
        _FakeResponse("https://one.example/final"),
    ]
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    monkeypatch.setattr(fetcher, "validate_public_url", checked.append)
    result = fetcher.fetch("https://one.example/start", Settings())
    assert result.body == b"<title>Safe</title>"
    assert checked == [
        "https://one.example/start",
        "https://one.example/final",
        "https://one.example/final",
    ]
