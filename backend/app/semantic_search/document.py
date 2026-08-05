import hashlib
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.models.discovery import Discovery

VERSION = "semantic-discovery-v1"


@dataclass(frozen=True)
class EmbeddingDocument:
    text: str
    fingerprint: bytes


def _normalize(value: str | None, cap: int) -> str | None:
    if not value:
        return None
    value = unicodedata.normalize("NFC", value.replace("\x00", ""))
    value = "".join(
        ch for ch in value if unicodedata.category(ch) not in {"Cc", "Cf"} or ch in "\n\t"
    )
    value = " ".join(value.split())
    return value[:cap] or None


def build_document(discovery: Discovery, max_chars: int = 12_000) -> EmbeddingDocument:
    metadata = (
        discovery.metadata_record
        if discovery.metadata_record and discovery.metadata_record.status == "succeeded"
        else None
    )
    summary = (
        discovery.ai_summary
        if discovery.ai_summary and discovery.ai_summary.status in {"succeeded", "stale"}
        else None
    )
    fields: list[tuple[str, str | None, int]] = [
        ("Custom title", discovery.custom_title, 300),
        ("Metadata title", metadata.title if metadata else None, 500),
        ("Metadata description", metadata.description if metadata else None, 4000),
        ("Site name", metadata.site_name if metadata else None, 200),
        ("Publisher", metadata.creator_or_publisher if metadata else None, 200),
        ("Platform", discovery.platform, 50),
        ("Hostname", urlsplit(discovery.canonical_url).hostname, 253),
        ("AI summary", summary.summary if summary else None, 600),
    ]
    if summary:
        fields.extend(("AI key point", value, 240) for value in summary.key_points[:5])
        fields.extend(("AI topic", value, 60) for value in summary.topics[:8])
    seen: set[str] = set()
    accepted: list[tuple[str, str]] = []
    for label, raw, cap in fields:
        value = _normalize(raw, cap)
        if value is None or value.casefold() in seen:
            continue
        seen.add(value.casefold())
        accepted.append((label, value))
    lines: list[str] = []
    for label, value in accepted:
        prefix = f"{label}: "
        remaining = max_chars - sum(len(line) + 1 for line in lines) - len(prefix) - 1
        if remaining <= 0:
            break
        if len(value) > remaining:
            value = value[: max(0, remaining - 1)] + "…"
        lines.append(prefix + value)
    text = "\n".join(lines) + ("\n" if lines else "")
    envelope = bytearray()
    for part in [
        VERSION.encode(),
        b"private-context-v1:false",
        *[f"{label}\0{value}".encode() for label, value in accepted],
        text.encode(),
    ]:
        envelope.extend(len(part).to_bytes(8, "big"))
        envelope.extend(part)
    return EmbeddingDocument(text=text, fingerprint=hashlib.sha256(envelope).digest())
