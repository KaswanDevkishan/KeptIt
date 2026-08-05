import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Response, status

from app.ai_summaries import service
from app.ai_summaries.schemas import GenerateRequest, PublicSummary, RegenerateRequest
from app.api.dependencies import CurrentUser, DbSession, TrustedOrigin
from app.core.config import get_settings
from app.services.discoveries import get_owned

router = APIRouter(prefix="/discoveries", tags=["AI summaries"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key")]
EMPTY_GENERATE_REQUEST = GenerateRequest()


@router.get("/{discovery_id}/summary", response_model=PublicSummary)
def get_summary(
    discovery_id: uuid.UUID, db: DbSession, user: CurrentUser, response: Response
) -> PublicSummary:
    response.headers["Cache-Control"] = "no-store"
    return service.public(get_owned(db, user.id, discovery_id), get_settings())


@router.post("/{discovery_id}/summary", response_model=PublicSummary, status_code=202)
def generate_summary(
    discovery_id: uuid.UUID,
    idempotency_key: IdempotencyKey,
    background: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
    response: Response,
    _origin: TrustedOrigin,
    payload: GenerateRequest = EMPTY_GENERATE_REQUEST,
) -> PublicSummary:
    settings = get_settings()
    discovery = get_owned(db, user.id, discovery_id)
    row, code = service.request_generation(
        db, discovery, user.id, settings, key=idempotency_key, regenerate=False
    )
    response.status_code = code
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = f"/api/v1/discoveries/{discovery_id}/summary"
    if code == 202:
        background.add_task(service.process, db, row.id, settings)
    return service.public(discovery, settings)


@router.post("/{discovery_id}/summary/regenerate", response_model=PublicSummary, status_code=202)
def regenerate_summary(
    discovery_id: uuid.UUID,
    payload: RegenerateRequest,
    idempotency_key: IdempotencyKey,
    background: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
    response: Response,
    _origin: TrustedOrigin,
) -> PublicSummary:
    settings = get_settings()
    discovery = get_owned(db, user.id, discovery_id)
    row, code = service.request_generation(
        db, discovery, user.id, settings, key=idempotency_key, regenerate=True
    )
    response.status_code = code
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = f"/api/v1/discoveries/{discovery_id}/summary"
    if code == 202:
        background.add_task(service.process, db, row.id, settings)
    return service.public(discovery, settings)


@router.delete("/{discovery_id}/summary", status_code=status.HTTP_204_NO_CONTENT)
def delete_summary(
    discovery_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> None:
    discovery = get_owned(db, user.id, discovery_id)
    if discovery.ai_summary is not None:
        db.delete(discovery.ai_summary)
        db.commit()
