import json
from dataclasses import dataclass
from typing import cast
from urllib.parse import parse_qs, quote, urlsplit

from app.core.config import Settings
from app.metadata.fetcher import FetchError, fetch
from app.metadata.parser import ParsedMetadata, parse_html


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    metadata: ParsedMetadata


def _safe_remote_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme.lower() in {"http", "https"} and parsed.hostname else None


def _json(url: str, settings: Settings) -> dict[str, object]:
    result = fetch(url, settings, accept_json=True)
    try:
        value = json.loads(result.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError(
            "invalid_provider_response", "The provider returned invalid metadata."
        ) from exc
    if not isinstance(value, dict):
        raise FetchError("invalid_provider_response", "The provider returned invalid metadata.")
    return value


def generic(url: str, settings: Settings) -> ProviderResult:
    result = fetch(url, settings)
    return ProviderResult("generic_html", parse_html(result.body, result.final_url))


def github(url: str, settings: Settings) -> ProviderResult:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if len(parts) < 2:
        return generic(url, settings)
    owner, repository = parts[:2]
    api_url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
    try:
        data = _json(api_url, settings)
    except FetchError as exc:
        if exc.code == "rate_limited":
            raise FetchError(
                "rate_limited", "GitHub metadata is temporarily rate limited."
            ) from exc
        return generic(url, settings)
    owner_value = data.get("owner")
    owner_data = cast(dict[str, object], owner_value) if isinstance(owner_value, dict) else {}
    return ProviderResult(
        "github_api",
        ParsedMetadata(
            title=str(data.get("full_name"))[:500] if data.get("full_name") else None,
            description=str(data.get("description"))[:2000] if data.get("description") else None,
            site_name="GitHub",
            creator_or_publisher=(
                str(owner_data.get("login"))[:300] if owner_data.get("login") else owner
            ),
            thumbnail_url=_safe_remote_url(owner_data.get("avatar_url")),
        ),
    )


def _youtube_video_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/").split("/", 1)[0] or None
    if parsed.path == "/watch":
        return parse_qs(parsed.query).get("v", [None])[0]
    parts = [part for part in parsed.path.split("/") if part]
    return parts[1] if len(parts) >= 2 and parts[0] in {"shorts", "embed"} else None


def youtube(url: str, settings: Settings) -> ProviderResult:
    if not settings.youtube_api_key:
        raise FetchError("provider_not_configured", "YouTube metadata is not configured.")
    video_id = _youtube_video_id(url)
    if not video_id:
        raise FetchError("unsupported_url", "This YouTube URL type is not supported.")
    api_url = (
        "https://www.googleapis.com/youtube/v3/videos?part=snippet&id="
        f"{quote(video_id, safe='')}&key={quote(settings.youtube_api_key, safe='')}"
    )
    data = _json(api_url, settings)
    items = data.get("items")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise FetchError("content_unavailable", "The YouTube video is unavailable.")
    item = cast(dict[str, object], items[0])
    snippet = item.get("snippet")
    if not isinstance(snippet, dict):
        raise FetchError("invalid_provider_response", "YouTube returned invalid metadata.")
    snippet = cast(dict[str, object], snippet)
    thumbnail_value = snippet.get("thumbnails")
    thumbnails = (
        cast(dict[str, object], thumbnail_value) if isinstance(thumbnail_value, dict) else {}
    )
    image = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default")
    image_url = image.get("url") if isinstance(image, dict) else None
    return ProviderResult(
        "youtube_api",
        ParsedMetadata(
            title=str(snippet.get("title"))[:500] if snippet.get("title") else None,
            description=(
                str(snippet.get("description"))[:2000] if snippet.get("description") else None
            ),
            site_name="YouTube",
            creator_or_publisher=(
                str(snippet.get("channelTitle"))[:300] if snippet.get("channelTitle") else None
            ),
            thumbnail_url=_safe_remote_url(image_url),
        ),
    )
