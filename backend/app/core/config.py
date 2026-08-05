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
    metadata_connect_timeout_seconds: float = 3.0
    metadata_read_timeout_seconds: float = 5.0
    metadata_max_response_bytes: int = 1_000_000
    metadata_max_redirects: int = 3
    metadata_user_agent: str = "KeptIt-Metadata/1.0 (+https://keptit.example)"
    youtube_api_key: str | None = None
    spaces_cursor_secret: str = "development-only-spaces-cursor-secret"
    ai_summaries_enabled: bool = False
    ai_real_provider_enabled: bool = False
    ai_summary_provider: str = "fake"
    openai_api_key: str | None = None
    ai_summary_model: str = "gpt-4.1-mini"
    ai_summary_prompt_version: str = "ai-summary-v1"
    ai_summary_timeout_seconds: float = 15.0
    ai_summary_max_input_chars: int = 6000
    ai_summary_max_output_tokens: int = 800
    ai_summary_daily_limit: int = 20
    ai_summary_concurrent_limit: int = 2
    ai_summary_regeneration_cooldown_seconds: int = 60
    ai_summary_max_retries: int = 2
    ai_summary_cost_input_rate: int | None = None
    ai_summary_cost_output_rate: int | None = None
    ai_summary_fake_behavior: str = "success"

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

    @field_validator("metadata_connect_timeout_seconds", "metadata_read_timeout_seconds")
    @classmethod
    def validate_metadata_timeout(cls, value: float) -> float:
        if not 0.1 <= value <= 30:
            raise ValueError("must be between 0.1 and 30 seconds")
        return value

    @field_validator("metadata_max_response_bytes")
    @classmethod
    def validate_metadata_size(cls, value: int) -> int:
        if not 16_384 <= value <= 5_000_000:
            raise ValueError("must be between 16384 and 5000000 bytes")
        return value

    @field_validator("metadata_max_redirects")
    @classmethod
    def validate_metadata_redirects(cls, value: int) -> int:
        if not 0 <= value <= 5:
            raise ValueError("must be between 0 and 5")
        return value

    @model_validator(mode="after")
    def require_secure_production_cookie(self) -> "Settings":
        if self.environment == "production" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires SESSION_COOKIE_SECURE=true")
        if self.environment == "production" and self.email_backend == "development_file":
            raise ValueError("development email backend cannot be used in production")
        if (
            self.environment == "production"
            and self.spaces_cursor_secret == "development-only-spaces-cursor-secret"
        ):
            raise ValueError("SPACES_CURSOR_SECRET must be changed in production")
        if self.ai_summary_provider not in {"fake", "openai"}:
            raise ValueError("AI_SUMMARY_PROVIDER must be fake or openai")
        if self.ai_summary_prompt_version != "ai-summary-v1":
            raise ValueError("AI_SUMMARY_PROMPT_VERSION must be ai-summary-v1")
        if self.environment == "production" and self.ai_summaries_enabled:
            raise ValueError("AI summaries require the production durable worker rollout")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
