from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DbSession
from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    service: str
    status: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report process health without depending on external services."""
    return HealthResponse(service=get_settings().app_name, status="ok")


@router.get(
    "/readiness",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def readiness_check(db: DbSession) -> ReadinessResponse | JSONResponse:
    """Report database readiness without exposing connection or schema details."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"service": get_settings().app_name, "status": "unavailable"},
        )
    return ReadinessResponse(service=get_settings().app_name, status="ok")
