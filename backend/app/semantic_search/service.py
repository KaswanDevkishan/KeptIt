import math
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.models.discovery import Discovery
from app.models.discovery_embedding import DiscoveryEmbedding
from app.models.space import Space, SpaceMembership
from app.models.tag import DiscoveryTag, Tag
from app.semantic_search.document import build_document
from app.semantic_search.providers import EmbeddingProviderError, get_provider
from app.semantic_search.schemas import (
    BackfillRequest,
    BackfillResponse,
    EmbeddingStatus,
    SemanticSearchItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.discoveries import get_owned


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _ensure_enabled(settings: Settings) -> None:
    if not settings.semantic_search_enabled:
        raise _error(503, "feature_disabled", "Meaning-based search is disabled.")


def _is_stale(row: DiscoveryEmbedding, discovery: Discovery, settings: Settings) -> bool:
    target = build_document(discovery, settings.embedding_max_input_chars)
    return (
        row.input_fingerprint != target.fingerprint
        or row.provider != settings.embedding_provider
        or row.model != settings.embedding_model
        or row.embedding_dimension != settings.embedding_dimension
        or row.document_version != settings.embedding_document_version
    )


def status(
    db: Session, user_id: uuid.UUID, discovery_id: uuid.UUID, settings: Settings
) -> EmbeddingStatus:
    discovery = get_owned(db, user_id, discovery_id)
    row = db.scalar(
        select(DiscoveryEmbedding).where(DiscoveryEmbedding.discovery_id == discovery.id)
    )
    if row is None:
        return EmbeddingStatus(
            status="unavailable",
            is_searchable=False,
            generated_at=None,
            last_attempted_at=None,
            can_index=settings.semantic_search_enabled,
            can_retry=False,
            retry_after_seconds=None,
        )
    state = (
        "stale" if row.status == "succeeded" and _is_stale(row, discovery, settings) else row.status
    )
    error = (
        {"code": row.failure_code, "message": row.failure_message_safe}
        if state == "failed" and row.failure_code and row.failure_message_safe
        else None
    )
    return EmbeddingStatus(
        status=state,
        is_searchable=state == "succeeded",
        generated_at=row.generated_at,
        last_attempted_at=row.last_attempted_at,
        can_index=settings.semantic_search_enabled and state in {"unavailable", "stale"},
        can_retry=settings.semantic_search_enabled
        and state in {"failed", "stale"}
        and row.retry_count < settings.embedding_max_retries,
        retry_after_seconds=None,
        error=error,
    )


def index(
    db: Session,
    user_id: uuid.UUID,
    discovery_id: uuid.UUID,
    settings: Settings,
    *,
    retry: bool = False,
) -> tuple[EmbeddingStatus, bool]:
    _ensure_enabled(settings)
    discovery = get_owned(db, user_id, discovery_id)
    document = build_document(discovery, settings.embedding_max_input_chars)
    if not document.text:
        raise _error(422, "embedding_input_unsupported", "This Discovery has no searchable text.")
    row = db.scalar(
        select(DiscoveryEmbedding)
        .where(DiscoveryEmbedding.discovery_id == discovery.id)
        .with_for_update()
    )
    if row and row.status in {"pending", "processing"} and not _is_stale(row, discovery, settings):
        return status(db, user_id, discovery_id, settings), False
    if row and row.status == "succeeded" and not _is_stale(row, discovery, settings):
        if retry:
            raise _error(
                409, "embedding_not_retryable", "The current embedding does not need retrying."
            )
        return status(db, user_id, discovery_id, settings), False
    if retry and row and row.status == "unsupported":
        raise _error(409, "embedding_not_retryable", "This Discovery cannot be embedded.")
    today = datetime.now(UTC).date()
    used = (
        db.scalar(
            select(func.count())
            .select_from(DiscoveryEmbedding)
            .join(Discovery)
            .where(
                Discovery.user_id == user_id,
                DiscoveryEmbedding.last_attempted_at
                >= datetime.combine(today, datetime.min.time(), UTC),
            )
        )
        or 0
    )
    if used >= settings.embedding_daily_index_limit:
        raise _error(429, "embedding_limit_exceeded", "The daily indexing limit has been reached.")
    if row is None:
        row = DiscoveryEmbedding(
            discovery_id=discovery.id,
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            embedding_dimension=settings.embedding_dimension,
            document_version=settings.embedding_document_version,
            input_fingerprint=document.fingerprint,
        )
        db.add(row)
    row.provider, row.model, row.embedding_dimension = (
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_dimension,
    )
    row.document_version, row.input_fingerprint = (
        settings.embedding_document_version,
        document.fingerprint,
    )
    row.status, row.last_attempted_at = "processing", datetime.now(UTC)
    row.processing_started_at = row.last_attempted_at
    row.processing_lease_expires_at = row.last_attempted_at + timedelta(
        seconds=max(30, int(settings.embedding_timeout_seconds * 3))
    )
    token = uuid.uuid4()
    row.generation_token = token
    db.commit()
    try:
        result = get_provider(settings).embed_one(
            document.text, "document", settings.embedding_timeout_seconds
        )
    except EmbeddingProviderError as exc:
        db.refresh(row)
        if row.generation_token != token:
            return status(db, user_id, discovery_id, settings), False
        row.status = "unsupported" if exc.code == "unsupported_input" else "failed"
        row.failure_code, row.failure_message_safe = exc.code, str(exc)[:240]
        row.retry_count += 1
        row.next_retry_at = datetime.now(UTC) + timedelta(
            seconds=settings.embedding_retry_backoff_seconds * 2 ** min(row.retry_count - 1, 6)
        )
        row.processing_lease_expires_at = None
        db.commit()
        return status(db, user_id, discovery_id, settings), True
    db.refresh(row)
    if row.generation_token == token and row.input_fingerprint == document.fingerprint:
        row.embedding, row.status, row.generated_at = result.vector, "succeeded", datetime.now(UTC)
        row.usage_tokens = result.usage_tokens
        row.estimated_cost_minor_units = (
            result.usage_tokens * settings.embedding_cost_rate
            if result.usage_tokens is not None and settings.embedding_cost_rate is not None
            else None
        )
        row.failure_code = row.failure_message_safe = None
        row.processing_lease_expires_at = row.next_retry_at = None
        db.commit()
    return status(db, user_id, discovery_id, settings), True


def backfill(
    db: Session, user_id: uuid.UUID, payload: BackfillRequest, settings: Settings
) -> BackfillResponse:
    _ensure_enabled(settings)
    if not settings.embedding_backfill_enabled:
        raise _error(503, "feature_disabled", "Embedding backfill is disabled.")
    discoveries = list(
        db.scalars(
            select(Discovery)
            .where(Discovery.user_id == user_id)
            .order_by(Discovery.created_at, Discovery.id)
        )
    )
    queued = skipped_current = skipped_unsupported = 0
    for discovery in discoveries:
        if queued >= payload.limit:
            break
        state = status(db, user_id, discovery.id, settings).status
        if state == "succeeded" or (state == "stale" and not payload.include_stale):
            skipped_current += 1
            continue
        if state == "unsupported":
            skipped_unsupported += 1
            continue
        index(db, user_id, discovery.id, settings, retry=state in {"failed", "stale"})
        queued += 1
    remaining = max(0, len(discoveries) - queued - skipped_current - skipped_unsupported)
    return BackfillResponse(
        requested=payload.limit,
        queued=queued,
        skipped_current=skipped_current,
        skipped_unsupported=skipped_unsupported,
        remaining_eligible=remaining,
    )


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    )


def _filtered_discoveries_statement(
    db: Session,
    user_id: uuid.UUID,
    payload: SemanticSearchRequest,
) -> tuple[Select[tuple[Discovery]], list[ColumnElement[bool]]]:
    """Build the shared owner/filter boundary for both retrieval branches."""
    conditions: list[ColumnElement[bool]] = [Discovery.user_id == user_id]
    if payload.filters.archive == "active":
        conditions.append(Discovery.archived_at.is_(None))
    elif payload.filters.archive == "archived":
        conditions.append(Discovery.archived_at.is_not(None))
    if payload.filters.platform:
        conditions.append(Discovery.platform.in_([item.value for item in payload.filters.platform]))
    if payload.filters.is_favourite is not None:
        conditions.append(Discovery.is_favourite == payload.filters.is_favourite)
    statement = select(Discovery)
    if payload.filters.tag_id:
        if (
            db.scalar(
                select(Tag.id).where(Tag.id == payload.filters.tag_id, Tag.user_id == user_id)
            )
            is None
        ):
            raise _error(404, "resource_not_found", "Resource not found.")
        statement = statement.join(DiscoveryTag, DiscoveryTag.discovery_id == Discovery.id)
        conditions.extend(
            [DiscoveryTag.user_id == user_id, DiscoveryTag.tag_id == payload.filters.tag_id]
        )
    if payload.filters.space_id:
        if (
            db.scalar(
                select(Space.id).where(
                    Space.id == payload.filters.space_id, Space.user_id == user_id
                )
            )
            is None
        ):
            raise _error(404, "resource_not_found", "Resource not found.")
        statement = statement.join(SpaceMembership, SpaceMembership.discovery_id == Discovery.id)
        conditions.extend(
            [
                SpaceMembership.user_id == user_id,
                SpaceMembership.space_id == payload.filters.space_id,
            ]
        )
    return statement, conditions


def build_postgresql_semantic_statement(
    db: Session,
    user_id: uuid.UUID,
    payload: SemanticSearchRequest,
    settings: Settings,
    query_vector: list[float],
) -> Select[tuple[Discovery, float]]:
    """Return the bounded pgvector query; exposed for SQL-construction tests."""
    base, conditions = _filtered_discoveries_statement(db, user_id, payload)
    distance = DiscoveryEmbedding.embedding.cosine_distance(query_vector)
    similarity = (1.0 - distance).label("semantic_similarity")
    return (
        base.add_columns(similarity)
        .join(DiscoveryEmbedding, DiscoveryEmbedding.discovery_id == Discovery.id)
        .where(
            *conditions,
            DiscoveryEmbedding.status == "succeeded",
            DiscoveryEmbedding.embedding.is_not(None),
            DiscoveryEmbedding.provider == settings.embedding_provider,
            DiscoveryEmbedding.model == settings.embedding_model,
            DiscoveryEmbedding.embedding_dimension == settings.embedding_dimension,
            DiscoveryEmbedding.document_version == settings.embedding_document_version,
            similarity >= settings.semantic_search_min_similarity,
        )
        .order_by(distance.asc(), Discovery.created_at.desc(), Discovery.id.desc())
        .limit(settings.semantic_search_semantic_candidates)
    )


def _postgresql_semantic_candidates(
    db: Session,
    user_id: uuid.UUID,
    payload: SemanticSearchRequest,
    settings: Settings,
    query_vector: list[float],
) -> list[tuple[Discovery, float]]:
    rows = db.execute(
        build_postgresql_semantic_statement(db, user_id, payload, settings, query_vector)
    ).all()
    # Fingerprint staleness depends on versioned application document construction. Filtering it
    # here never exposes a vector and prevents a changed document from influencing final ranking.
    return [
        (discovery, max(-1.0, min(1.0, float(similarity))))
        for discovery, similarity in rows
        if discovery.embedding_record is not None
        and not _is_stale(discovery.embedding_record, discovery, settings)
    ]


def _sqlite_test_semantic_candidates(
    owned: list[Discovery], query_vector: list[float], settings: Settings
) -> list[tuple[Discovery, float]]:
    """SQLite-only test fallback; production PostgreSQL must never use this path."""
    semantic: list[tuple[Discovery, float]] = []
    for discovery in owned:
        row = discovery.embedding_record
        if (
            row
            and row.status == "succeeded"
            and row.embedding is not None
            and row.provider == settings.embedding_provider
            and row.model == settings.embedding_model
            and row.embedding_dimension == settings.embedding_dimension
            and row.document_version == settings.embedding_document_version
            and not _is_stale(row, discovery, settings)
        ):
            score = _cosine(list(row.embedding), query_vector)
            if score >= settings.semantic_search_min_similarity:
                semantic.append((discovery, score))
    semantic.sort(key=lambda pair: (-pair[1], -pair[0].created_at.timestamp(), str(pair[0].id)))
    return semantic[: settings.semantic_search_semantic_candidates]


def search(
    db: Session, user_id: uuid.UUID, payload: SemanticSearchRequest, settings: Settings
) -> SemanticSearchResponse:
    statement, conditions = _filtered_discoveries_statement(db, user_id, payload)
    owned = list(
        db.scalars(
            statement.where(*conditions).order_by(Discovery.created_at.desc(), Discovery.id.desc())
        )
    )
    term = payload.query.casefold()
    keyword = [
        d
        for d in owned
        if term
        in " ".join(
            filter(
                None,
                [
                    d.custom_title,
                    d.personal_note,
                    d.original_url,
                    d.metadata_record.title if d.metadata_record else None,
                ],
            )
        ).casefold()
    ][: settings.semantic_search_keyword_candidates]
    semantic: list[tuple[Discovery, float]] = []
    fallback = None
    if payload.mode != "keyword":
        if not settings.semantic_search_enabled:
            if payload.mode == "semantic":
                _ensure_enabled(settings)
            fallback = "feature_disabled"
        else:
            try:
                query_vector = (
                    get_provider(settings)
                    .embed_one(payload.query, "query", settings.embedding_timeout_seconds)
                    .vector
                )
                dialect = db.get_bind().dialect.name
                semantic = (
                    _postgresql_semantic_candidates(db, user_id, payload, settings, query_vector)
                    if dialect == "postgresql"
                    else _sqlite_test_semantic_candidates(owned, query_vector, settings)
                )
                if not semantic:
                    fallback = (
                        "no_current_embeddings"
                        if not any(d.embedding_record for d in owned)
                        else "no_confident_semantic_match"
                    )
            except EmbeddingProviderError as exc:
                if payload.mode == "semantic":
                    raise _error(
                        503,
                        "provider_temporarily_unavailable",
                        "Meaning-based search is temporarily unavailable.",
                    ) from exc
                fallback = {
                    "timeout": "provider_timeout",
                    "rate_limited": "provider_rate_limited",
                }.get(exc.code, "provider_unavailable")
    ranked: list[tuple[Discovery, float, bool, list[str]]]
    if payload.mode == "semantic" and not fallback:
        ranked = [(d, s, False, ["summary"]) for d, s in semantic]
    else:
        scores: dict[uuid.UUID, tuple[Discovery, float, float | None, bool]] = {}
        for rank, discovery in enumerate(keyword, 1):
            scores[discovery.id] = (discovery, 1 / (60 + rank), None, True)
        for rank, (discovery, similarity) in enumerate(semantic, 1):
            current = scores.get(discovery.id, (discovery, 0.0, similarity, False))
            scores[discovery.id] = (discovery, current[1] + 1 / (60 + rank), similarity, current[3])
        fused_rows: list[tuple[Discovery, float, float | None, bool, bool]] = []
        for discovery, fused, stored_similarity, kw in scores.values():
            exact = term in {
                (discovery.custom_title or "").strip().casefold(),
                ((discovery.metadata_record.title or "") if discovery.metadata_record else "")
                .strip()
                .casefold(),
            }
            fused_rows.append(
                (discovery, fused + (0.01 if exact else 0), stored_similarity, kw, exact)
            )
        fused_rows.sort(
            key=lambda value: (
                -value[1],
                -(value[2] or -1),
                -value[0].created_at.timestamp(),
                str(value[0].id),
            )
        )
        ranked = [
            (d, s, kw, ["custom_title" if exact else "keyword"] if kw else ["summary"])
            for d, s, _similarity, kw, exact in fused_rows
        ]
    indexed_count = sum(
        1
        for d in owned
        if d.embedding_record
        and d.embedding_record.status == "succeeded"
        and not _is_stale(d.embedding_record, d, settings)
    )
    coverage = (
        "none" if indexed_count == 0 else "complete" if indexed_count == len(owned) else "partial"
    )
    effective = "keyword" if payload.mode == "keyword" or fallback else payload.mode
    items = [
        SemanticSearchItem(
            discovery=d,
            relevance={
                "score": min(1.0, score),
                "semantic_similarity": next((sim for sd, sim in semantic if sd.id == d.id), None),
                "keyword_match": kw,
                "match_reasons": reasons,
            },
        )
        for d, score, kw, reasons in ranked[: payload.limit]
    ]
    return SemanticSearchResponse(
        items=items,
        search={
            "requested_mode": payload.mode,
            "effective_mode": effective,
            "fallback_reason": fallback,
            "index_coverage": coverage,
            "indexed_count": indexed_count,
            "eligible_count": len(owned),
            "ranking_version": "semantic-hybrid-v1",
        },
    )
