from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.metadata import providers
from app.metadata.fetcher import FetchError
from app.models.discovery import Discovery, MetadataRecord

UNSUPPORTED_PLATFORMS = {"instagram", "tiktok", "reddit", "x"}


def ensure_record(discovery: Discovery) -> MetadataRecord:
    if discovery.metadata_record is None:
        discovery.metadata_record = MetadataRecord(status="pending", provider="pending")
    return discovery.metadata_record


def enrich(db: Session, discovery: Discovery, settings: Settings) -> MetadataRecord:
    record = ensure_record(discovery)
    now = datetime.now(UTC)
    record.status = "processing"
    record.last_attempted_at = now
    record.failure_code = None
    record.failure_message_safe = None
    db.commit()
    try:
        if discovery.platform in UNSUPPORTED_PLATFORMS:
            raise FetchError(
                "platform_unsupported",
                "Official metadata access is not configured for this platform.",
            )
        if discovery.platform == "youtube":
            result = providers.youtube(discovery.original_url, settings)
        elif discovery.platform == "github":
            result = providers.github(discovery.original_url, settings)
        else:
            result = providers.generic(discovery.original_url, settings)
        metadata = result.metadata
        record.status = "succeeded"
        record.provider = result.provider
        record.title = metadata.title
        record.description = metadata.description
        record.site_name = metadata.site_name
        record.creator_or_publisher = metadata.creator_or_publisher
        record.thumbnail_url = metadata.thumbnail_url
        record.published_at = metadata.published_at
        record.fetched_at = datetime.now(UTC)
    except FetchError as exc:
        record.status = (
            "unsupported"
            if exc.code in {"platform_unsupported", "provider_not_configured", "unsupported_url"}
            else "failed"
        )
        record.provider = discovery.platform
        record.failure_code = exc.code[:80]
        record.failure_message_safe = str(exc)[:500]
    record.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(record)
    return record
