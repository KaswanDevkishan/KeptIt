from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized[:limit] or None


def _safe_url(value: str | None, base_url: str) -> str | None:
    if not value:
        return None
    resolved = urljoin(base_url, value.strip())
    return resolved if urlsplit(resolved).scheme.lower() in {"http", "https"} else None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


@dataclass(frozen=True)
class ParsedMetadata:
    title: str | None = None
    description: str | None = None
    site_name: str | None = None
    creator_or_publisher: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}
        self.in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() != "meta":
            return
        key = (values.get("property") or values.get("name") or "").lower()
        content = values.get("content")
        if key and content and key not in self.values:
            self.values[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title and sum(map(len, self.title_parts)) < 1000:
            self.title_parts.append(data)


def parse_html(body: bytes, final_url: str) -> ParsedMetadata:
    parser = _MetadataParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    values = parser.values
    title = values.get("og:title") or values.get("twitter:title") or "".join(parser.title_parts)
    description = (
        values.get("og:description")
        or values.get("twitter:description")
        or values.get("description")
    )
    author = values.get("article:author") or values.get("author") or values.get("publisher")
    published = values.get("article:published_time") or values.get("date")
    return ParsedMetadata(
        title=_clean(title, 500),
        description=_clean(description, 2000),
        site_name=_clean(values.get("og:site_name"), 200),
        creator_or_publisher=_clean(author, 300),
        thumbnail_url=_safe_url(values.get("og:image") or values.get("twitter:image"), final_url),
        published_at=_date(published),
    )
