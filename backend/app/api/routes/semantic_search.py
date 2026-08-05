import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.dependencies import AppSettings, CurrentUser, DbSession, TrustedOrigin
from app.semantic_search import service
from app.semantic_search.schemas import (
    BackfillRequest,
    BackfillResponse,
    EmbeddingStatus,
    EmptyRequest,
    RetryRequest,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

router = APIRouter(tags=["semantic-search"])


def validate_key(value: str) -> None:
    if not 16 <= len(value) <= 128 or not value.isascii() or not value.isprintable():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "Idempotency-Key must be 16-128 printable ASCII characters.",
            },
        )


@router.post("/search/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    payload: SemanticSearchRequest,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
    settings: AppSettings,
) -> SemanticSearchResponse:
    return service.search(db, user.id, payload, settings)


@router.get("/discoveries/{discovery_id}/embedding/status", response_model=EmbeddingStatus)
def embedding_status(
    discovery_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    response: Response,
) -> EmbeddingStatus:
    response.headers["Cache-Control"] = "no-store"
    return service.status(db, user.id, discovery_id, settings)


@router.post("/discoveries/{discovery_id}/embedding", response_model=EmbeddingStatus)
def index_embedding(
    discovery_id: uuid.UUID,
    _payload: EmptyRequest,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
    settings: AppSettings,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> EmbeddingStatus:
    validate_key(idempotency_key)
    result, created = service.index(db, user.id, discovery_id, settings)
    response.status_code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
    response.headers["Location"] = f"/api/v1/discoveries/{discovery_id}/embedding/status"
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/discoveries/{discovery_id}/embedding/retry", response_model=EmbeddingStatus)
def retry_embedding(
    discovery_id: uuid.UUID,
    _payload: RetryRequest,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
    settings: AppSettings,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> EmbeddingStatus:
    validate_key(idempotency_key)
    result, created = service.index(db, user.id, discovery_id, settings, retry=True)
    response.status_code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/embeddings/backfill", response_model=BackfillResponse)
def backfill_embeddings(
    payload: BackfillRequest,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
    settings: AppSettings,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> BackfillResponse:
    validate_key(idempotency_key)
    result = service.backfill(db, user.id, payload, settings)
    response.status_code = status.HTTP_202_ACCEPTED if result.queued else status.HTTP_200_OK
    response.headers["Cache-Control"] = "no-store"
    return result
