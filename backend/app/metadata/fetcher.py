import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import Settings


class FetchError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchResult:
    body: bytes
    final_url: str
    content_type: str
    status_code: int


def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise FetchError("unsafe_url", "Only public HTTP and HTTPS URLs are supported.")
    if parsed.username is not None or parsed.password is not None:
        raise FetchError("embedded_credentials", "URLs containing credentials are not supported.")
    if parsed.hostname.lower() == "localhost":
        raise FetchError("unsafe_host", "Local network targets are not permitted.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise FetchError("dns_failure", "The destination hostname could not be resolved.") from exc
    if not addresses:
        raise FetchError("dns_failure", "The destination hostname could not be resolved.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise FetchError("unsafe_host", "The destination address is invalid.") from exc
        if not ip.is_global:
            raise FetchError(
                "unsafe_host", "Local or non-public network targets are not permitted."
            )


def fetch(url: str, settings: Settings, *, accept_json: bool = False) -> FetchResult:
    current = url
    headers = {
        "User-Agent": settings.metadata_user_agent,
        "Accept": "application/json" if accept_json else "text/html,application/xhtml+xml",
    }
    timeout = httpx.Timeout(
        connect=settings.metadata_connect_timeout_seconds,
        read=settings.metadata_read_timeout_seconds,
        write=settings.metadata_read_timeout_seconds,
        pool=settings.metadata_connect_timeout_seconds,
    )
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
            for redirect_count in range(settings.metadata_max_redirects + 1):
                validate_public_url(current)
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError(
                                "invalid_redirect", "The destination returned an invalid redirect."
                            )
                        if redirect_count >= settings.metadata_max_redirects:
                            raise FetchError(
                                "too_many_redirects", "The destination redirected too many times."
                            )
                        current = urljoin(current, location)
                        validate_public_url(current)
                        continue
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    allowed = (
                        {"application/json"}
                        if accept_json
                        else {"text/html", "application/xhtml+xml"}
                    )
                    if content_type not in allowed:
                        raise FetchError(
                            "unsupported_content_type",
                            "The destination is not a supported metadata document.",
                        )
                    if response.status_code >= 400:
                        code = "rate_limited" if response.status_code == 429 else "upstream_error"
                        raise FetchError(
                            code, "The metadata provider could not return this content."
                        )
                    parts: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > settings.metadata_max_response_bytes:
                            raise FetchError(
                                "response_too_large",
                                "The metadata response exceeded the size limit.",
                            )
                        parts.append(chunk)
                    return FetchResult(
                        b"".join(parts), str(response.url), content_type, response.status_code
                    )
    except httpx.TimeoutException as exc:
        raise FetchError("timeout", "The metadata request timed out.") from exc
    except httpx.HTTPError as exc:
        raise FetchError("network_error", "The metadata request failed safely.") from exc
    raise FetchError("too_many_redirects", "The destination redirected too many times.")
