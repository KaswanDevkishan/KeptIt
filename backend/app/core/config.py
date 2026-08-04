from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KeptIt API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://keptit:keptit@localhost:5432/keptit"
    cors_origins: list[AnyHttpUrl] = [AnyHttpUrl("http://localhost:5173")]
    session_cookie_name: str = "keptit_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_path: str = "/"
    session_duration_seconds: int = 60 * 60 * 24 * 30
    frontend_password_reset_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173/reset-password")
    password_reset_token_lifetime_seconds: int = 60 * 30
    email_backend: str = "development_file"
    development_email_outbox_path: Path = Path(".local/password-reset-outbox.jsonl")

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("must be one of: lax, strict, none")
        return normalized

    @field_validator("session_duration_seconds")
    @classmethod
    def validate_session_duration(cls, value: int) -> int:
        if not 300 <= value <= 60 * 60 * 24 * 365:
            raise ValueError("must be between 300 and 31536000 seconds")
        return value

    @field_validator("password_reset_token_lifetime_seconds")
    @classmethod
    def validate_password_reset_lifetime(cls, value: int) -> int:
        if not 300 <= value <= 60 * 60 * 24:
            raise ValueError("must be between 300 and 86400 seconds")
        return value

    @field_validator("email_backend")
    @classmethod
    def validate_email_backend(cls, value: str) -> str:
        if value not in {"development_file", "disabled"}:
            raise ValueError("must be one of: development_file, disabled")
        return value

    @model_validator(mode="after")
    def require_secure_production_cookie(self) -> "Settings":
        if self.environment == "production" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires SESSION_COOKIE_SECURE=true")
        if self.environment == "production" and self.email_backend == "development_file":
            raise ValueError("development email backend cannot be used in production")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
