import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_summaries.providers import ProviderFailure, get_provider
from app.ai_summaries.schemas import PublicError, PublicSummary, SummaryInput
from app.core.config import Settings
from app.models.ai_summary import AISummary, AISummaryIdempotencyKey
from app.models.discovery import Discovery

SAFE_FAILURES = {
    "timeout": "AI summary generation timed out. Try again later.",
    "rate_limited": "AI summary generation is temporarily rate limited. Try again later.",
    "unavailable": "AI summary generation is temporarily unavailable. Try again later.",
    "invalid_provider_output": "AI summary generation returned an invalid result. Try again.",
    "failure": "AI summary generation failed. Try again later.",
}
RETRYABLE = set(SAFE_FAILURES)


def approved_input(discovery: Discovery, max_chars: int) -> SummaryInput:
    metadata = discovery.metadata_record

    def bounded(value: str | None) -> str | None:
        if value is None:
            return None
        clean = " ".join(value.split()).replace("\x00", "")
        return clean[:max_chars] or None

    return SummaryInput(
        title=bounded(metadata.title if metadata else None),
        description=bounded(metadata.description if metadata else None),
        site_name=bounded(metadata.site_name if metadata else None),
        creator_or_publisher=bounded(metadata.creator_or_publisher if metadata else None),
        published_date=metadata.published_at.date().isoformat()
        if metadata and metadata.published_at
        else None,
        platform=discovery.platform,
        canonical_hostname=(urlsplit(discovery.canonical_url).hostname or "").lower(),
    )


def fingerprint(data: SummaryInput) -> bytes:
    canonical = json.dumps(
        {"input_policy_version": 1, **data.model_dump()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).digest()


def configured(settings: Settings) -> bool:
    if settings.ai_summary_provider == "fake":
        return True
    key = (
        settings.gemini_api_key
        if settings.ai_summary_provider == "gemini"
        else settings.openai_api_key
    )
    return bool(settings.ai_real_provider_enabled and key)


def public(discovery: Discovery, settings: Settings) -> PublicSummary:
    row = discovery.ai_summary
    if row is None:
        data = approved_input(discovery, settings.ai_summary_max_input_chars)
        reason = (
            "disabled"
            if not settings.ai_summaries_enabled
            else "provider_unavailable"
            if not configured(settings)
            else "insufficient_data"
            if not (data.title or data.description)
            else None
        )
        return PublicSummary(
            status="unavailable",
            availability_reason=reason,
            can_generate=reason is None,
        )
    current = fingerprint(approved_input(discovery, settings.ai_summary_max_input_chars))
    status = row.status
    if row.summary and row.input_fingerprint != current:
        status = "stale"
    error = (
        PublicError(code=row.failure_code, message=row.failure_message_safe)
        if row.failure_code and row.failure_message_safe
        else None
    )
    has_output = row.summary is not None
    return PublicSummary(
        status=status,
        summary=row.summary if has_output else None,
        key_points=row.key_points if has_output else [],
        topics=row.topics if has_output else [],
        entities=row.entities if has_output else [],
        language=row.language if has_output else None,
        confidence=float(row.confidence) if row.confidence is not None and has_output else None,
        insufficiency_reason=row.insufficiency_reason,
        generated_at=row.generated_at,
        last_attempted_at=row.last_attempted_at,
        is_regenerating=row.is_regenerating,
        last_attempt_error=error if has_output else None,
        error=error if status == "failed" else None,
        can_generate=False,
        can_retry=status == "failed"
        and (row.failure_code in RETRYABLE)
        and row.retry_count < settings.ai_summary_max_retries,
        can_regenerate=status in {"succeeded", "stale", "insufficient_data", "unsupported"},
        retry_after_seconds=None,
    )


def _problem(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def recover_interrupted(db: Session, discovery: Discovery, settings: Settings) -> None:
    """Convert expired in-process work into a safe retryable state on the next request."""
    row = discovery.ai_summary
    if row is None:
        return
    now = datetime.now(UTC)
    pending_expired = (
        (row.status == "pending" or row.is_regenerating)
        and row.last_attempted_at is not None
        and row.last_attempted_at
        < now - timedelta(seconds=max(60, int(settings.ai_summary_timeout_seconds * 3)))
    )
    processing_expired = (
        (row.status == "processing" or row.is_regenerating)
        and row.processing_lease_expires_at is not None
        and row.processing_lease_expires_at < now
    )
    if not (pending_expired or processing_expired):
        return
    if not row.is_regenerating:
        row.status = "failed"
    row.is_regenerating = False
    row.failure_code = "unavailable"
    row.failure_message_safe = SAFE_FAILURES["unavailable"]
    row.processing_started_at = None
    row.processing_lease_expires_at = None
    row.available_at = None
    row.generation_token = uuid.uuid4()
    db.commit()


def request_generation(
    db: Session,
    discovery: Discovery,
    user_id: uuid.UUID,
    settings: Settings,
    *,
    key: str,
    regenerate: bool,
) -> tuple[AISummary, int]:
    if not settings.ai_summaries_enabled:
        raise _problem(503, "feature_disabled", "AI summaries are not enabled.")
    if not configured(settings):
        raise _problem(503, "provider_not_configured", "AI summary generation is not configured.")
    if len(key) < 16 or len(key) > 128 or not key.isascii() or not key.isprintable():
        raise _problem(422, "validation_error", "Idempotency-Key is invalid.")
    now = datetime.now(UTC)
    action = "regenerate" if regenerate else "generate"
    key_hash = hashlib.sha256(key.encode()).digest()
    payload_hash = hashlib.sha256(action.encode()).digest()
    replay = db.scalar(
        select(AISummaryIdempotencyKey).where(
            AISummaryIdempotencyKey.user_id == user_id,
            AISummaryIdempotencyKey.discovery_id == discovery.id,
            AISummaryIdempotencyKey.action == action,
            AISummaryIdempotencyKey.key_hash == key_hash,
        )
    )
    if replay:
        if replay.payload_fingerprint != payload_hash:
            raise _problem(409, "idempotency_key_reused", "The idempotency key was already used.")
        if discovery.ai_summary is None:
            raise _problem(
                409, "idempotency_key_reused", "The idempotent result is no longer available."
            )
        return discovery.ai_summary, replay.result_http_status
    row = discovery.ai_summary
    if row and (row.status in {"pending", "processing"} or row.is_regenerating):
        raise _problem(
            409, "summary_generation_in_progress", "AI summary generation is already in progress."
        )
    if regenerate and (
        row is None or row.status not in {"succeeded", "insufficient_data", "unsupported"}
    ):
        raise _problem(422, "validation_error", "There is no summary to regenerate.")
    if regenerate and row and row.last_attempted_at:
        elapsed = (now - row.last_attempted_at).total_seconds()
        if elapsed < settings.ai_summary_regeneration_cooldown_seconds:
            raise _problem(429, "regeneration_cooldown", "Wait before regenerating this summary.")
    since = now - timedelta(days=1)
    count = (
        db.scalar(
            select(func.count())
            .select_from(AISummary)
            .join(Discovery)
            .where(Discovery.user_id == user_id, AISummary.last_attempted_at >= since)
        )
        or 0
    )
    if count >= settings.ai_summary_daily_limit:
        raise _problem(
            429, "summary_limit_exceeded", "The daily AI summary limit has been reached."
        )
    active = (
        db.scalar(
            select(func.count())
            .select_from(AISummary)
            .join(Discovery)
            .where(Discovery.user_id == user_id, AISummary.status.in_(["pending", "processing"]))
        )
        or 0
    )
    if active >= settings.ai_summary_concurrent_limit:
        raise _problem(429, "summary_limit_exceeded", "Too many AI summaries are in progress.")
    if row is None:
        row = AISummary(discovery_id=discovery.id)
        db.add(row)
        discovery.ai_summary = row
    row.is_regenerating = regenerate and row.summary is not None
    if not row.is_regenerating:
        row.status = "pending"
    row.available_at = now
    row.last_attempted_at = now
    row.generation_token = uuid.uuid4()
    row.failure_code = None
    row.failure_message_safe = None
    db.add(
        AISummaryIdempotencyKey(
            user_id=user_id,
            discovery_id=discovery.id,
            action=action,
            key_hash=key_hash,
            payload_fingerprint=payload_hash,
            result_http_status=202,
            expires_at=now + timedelta(days=1),
        )
    )
    db.commit()
    db.refresh(row)
    return row, 202


def process(db: Session, summary_id: uuid.UUID, settings: Settings) -> None:
    row = db.get(AISummary, summary_id)
    if row is None:
        return
    token = row.generation_token
    now = datetime.now(UTC)
    if not row.is_regenerating:
        row.status = "processing"
    row.processing_started_at = now
    row.processing_lease_expires_at = now + timedelta(
        seconds=max(30, int(settings.ai_summary_timeout_seconds * 2))
    )
    db.commit()
    discovery = row.discovery
    data = approved_input(discovery, settings.ai_summary_max_input_chars)
    if (
        discovery.metadata_record
        and discovery.metadata_record.status == "unsupported"
        and not (data.title or data.description)
    ):
        row.status = "unsupported"
        row.is_regenerating = False
        row.processing_started_at = None
        row.processing_lease_expires_at = None
        db.commit()
        return
    provider = get_provider(settings)
    try:
        result = provider.generate(
            data,
            model=settings.ai_summary_model,
            prompt_version=settings.ai_summary_prompt_version,
            timeout_seconds=settings.ai_summary_timeout_seconds,
            max_output_tokens=settings.ai_summary_max_output_tokens,
        )
        db.refresh(row)
        if row.generation_token != token:
            return
        output = result.output
        row.status = "insufficient_data" if output.summary is None else "succeeded"
        row.summary = output.summary
        row.key_points = output.key_points
        row.topics = output.topics
        row.entities = [item.model_dump(mode="json") for item in output.entities]
        row.language = output.language
        row.confidence = Decimal(str(output.confidence))
        row.insufficiency_reason = output.insufficiency_reason
        row.provider = settings.ai_summary_provider
        row.model = settings.ai_summary_model
        row.prompt_version = settings.ai_summary_prompt_version
        row.input_fingerprint = fingerprint(data)
        row.generated_at = datetime.now(UTC) if output.summary else None
        row.usage_input_tokens = result.input_tokens
        row.usage_output_tokens = result.output_tokens
        if (
            settings.ai_summary_cost_input_rate is not None
            and settings.ai_summary_cost_output_rate is not None
            and result.input_tokens is not None
            and result.output_tokens is not None
        ):
            row.estimated_cost_minor_units = (
                result.input_tokens * settings.ai_summary_cost_input_rate
                + result.output_tokens * settings.ai_summary_cost_output_rate
            )
        else:
            row.estimated_cost_minor_units = None
        row.failure_code = None
        row.failure_message_safe = None
    except ProviderFailure as exc:
        row.retry_count += 1
        row.failure_code = exc.code
        row.failure_message_safe = SAFE_FAILURES.get(exc.code, SAFE_FAILURES["failure"])
        if not row.is_regenerating:
            row.status = "failed"
    finally:
        row.is_regenerating = False
        row.processing_started_at = None
        row.processing_lease_expires_at = None
        row.available_at = None
        db.commit()
