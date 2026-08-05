from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.ai_summaries import router as ai_summaries_router
from app.api.routes.auth import router as auth_router
from app.api.routes.discoveries import router as discoveries_router
from app.api.routes.health import router as health_router
from app.api.routes.spaces import router as spaces_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            error = detail
        else:
            error = {"code": "request_error", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request contains invalid fields.",
                }
            },
        )

    application.include_router(health_router, prefix=settings.api_v1_prefix)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(users_router, prefix=settings.api_v1_prefix)
    application.include_router(discoveries_router, prefix=settings.api_v1_prefix)
    application.include_router(ai_summaries_router, prefix=settings.api_v1_prefix)
    application.include_router(spaces_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
