import hashlib
import ipaddress
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_URL_LENGTH = 2048
NORMALIZATION_VERSION = 1
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


class InvalidUrlError(ValueError):
    pass


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    REDDIT = "reddit"
    X = "x"
    GITHUB = "github"
    GENERIC_WEB = "generic_web"


@dataclass(frozen=True)
class NormalizedUrl:
    original_url: str
    canonical_url: str
    canonical_url_hash: bytes
    platform: Platform
    normalization_version: int = NORMALIZATION_VERSION


def _reject_unsafe_host(hostname: str) -> None:
    host = hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise InvalidUrlError("Local and private network URLs are not allowed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise InvalidUrlError("Local and private network URLs are not allowed.")


def detect_platform(hostname: str) -> Platform:
    host = hostname.rstrip(".").lower()
    if host in {"instagram.com", "www.instagram.com"}:
        return Platform.INSTAGRAM
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return Platform.YOUTUBE
    if host in {"tiktok.com", "www.tiktok.com"}:
        return Platform.TIKTOK
    if host in {"reddit.com", "www.reddit.com", "old.reddit.com"}:
        return Platform.REDDIT
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        return Platform.X
    if host in {"github.com", "www.github.com"}:
        return Platform.GITHUB
    return Platform.GENERIC_WEB


def normalize_url(value: str) -> NormalizedUrl:
    if not value or len(value) > MAX_URL_LENGTH or value != value.strip():
        raise InvalidUrlError("Enter a valid URL up to 2,048 characters.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise InvalidUrlError("Enter a valid HTTP or HTTPS URL.") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidUrlError("Enter a valid HTTP or HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidUrlError("URLs containing credentials are not allowed.")
    hostname = parsed.hostname.lower()
    _reject_unsafe_host(hostname)
    if any(char.isspace() for char in hostname) or "." not in hostname:
        raise InvalidUrlError("Enter a URL with a valid hostname.")
    try:
        hostname.encode("idna")
    except UnicodeError as exc:
        raise InvalidUrlError("Enter a URL with a valid hostname.") from exc
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"
    query = [
        pair
        for pair in parse_qsl(parsed.query, keep_blank_values=True)
        if pair[0].lower() not in TRACKING_PARAMETERS
    ]
    query.sort(key=lambda pair: (pair[0], pair[1]))
    canonical = urlunsplit((scheme, netloc, parsed.path or "/", urlencode(query, doseq=True), ""))
    if len(canonical) > MAX_URL_LENGTH:
        raise InvalidUrlError("The normalized URL is too long.")
    return NormalizedUrl(
        value, canonical, hashlib.sha256(canonical.encode()).digest(), detect_platform(hostname)
    )
