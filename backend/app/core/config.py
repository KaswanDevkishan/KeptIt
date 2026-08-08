from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KeptIt API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://keptit:keptit@localhost:5432/keptit"
    database_migration_url: str | None = None
    database_connect_timeout_seconds: int = 5
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
    gemini_api_key: str | None = None
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
    semantic_search_enabled: bool = False
    embedding_real_provider_enabled: bool = False
    embedding_provider: str = "fake"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_document_version: str = "semantic-discovery-v1"
    embedding_timeout_seconds: float = 10.0
    embedding_max_input_chars: int = 12_000
    embedding_daily_index_limit: int = 100
    semantic_search_daily_query_limit: int = 100
    semantic_search_max_query_chars: int = 500
    semantic_search_default_limit: int = 20
    semantic_search_max_limit: int = 50
    semantic_search_min_similarity: float = 0.35
    semantic_search_semantic_candidates: int = 100
    semantic_search_keyword_candidates: int = 100
    embedding_max_retries: int = 3
    embedding_retry_backoff_seconds: int = 30
    embedding_batch_size: int = 20
    embedding_cost_rate: int | None = None
    embedding_fake_behavior: str = "success"
    embedding_backfill_enabled: bool = True
    log_level: str = "INFO"

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

    @field_validator("database_connect_timeout_seconds")
    @classmethod
    def validate_database_connect_timeout(cls, value: int) -> int:
        if not 1 <= value <= 30:
            raise ValueError("must be between 1 and 30 seconds")
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

    @field_validator(
        "database_migration_url",
        "openai_api_key",
        "gemini_api_key",
        "youtube_api_key",
        "ai_summary_cost_input_rate",
        "ai_summary_cost_output_rate",
        "embedding_cost_rate",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("must be a standard Python log level")
        return normalized

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
        if self.environment == "production" and self.session_cookie_samesite not in {"lax", "none"}:
            raise ValueError("production SESSION_COOKIE_SAMESITE must be lax or none")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SameSite=None requires SESSION_COOKIE_SECURE=true")
        if self.environment == "production" and self.email_backend == "development_file":
            raise ValueError("development email backend cannot be used in production")
        if self.environment == "production":
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must contain at least one frontend origin")
            for origin in self.cors_origins:
                parsed = urlsplit(str(origin))
                if parsed.scheme != "https":
                    raise ValueError("production CORS origins must use HTTPS")
                if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("production CORS origins must not use localhost")
                if (
                    parsed.username
                    or parsed.password
                    or parsed.path not in {"", "/"}
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("CORS_ORIGINS entries must be origins without paths")
            reset_origin = urlsplit(str(self.frontend_password_reset_url))
            allowed_origins = {str(origin).rstrip("/") for origin in self.cors_origins}
            if f"{reset_origin.scheme}://{reset_origin.netloc}" not in allowed_origins:
                raise ValueError("FRONTEND_PASSWORD_RESET_URL must use an allowed frontend origin")
        if (
            self.environment == "production"
            and self.spaces_cursor_secret == "development-only-spaces-cursor-secret"
        ):
            raise ValueError("SPACES_CURSOR_SECRET must be changed in production")
        if self.ai_summary_provider not in {"fake", "openai", "gemini"}:
            raise ValueError("AI_SUMMARY_PROVIDER must be fake, openai, or gemini")
        if self.ai_summary_prompt_version != "ai-summary-v1":
            raise ValueError("AI_SUMMARY_PROMPT_VERSION must be ai-summary-v1")
        if (
            self.ai_summaries_enabled
            and self.ai_summary_provider == "openai"
            and (not self.ai_real_provider_enabled or not self.openai_api_key)
        ):
            raise ValueError("OpenAI AI summaries require real-provider enablement and a key")
        if (
            self.ai_summaries_enabled
            and self.ai_summary_provider == "gemini"
            and (not self.ai_real_provider_enabled or not self.gemini_api_key)
        ):
            raise ValueError("Gemini AI summaries require real-provider enablement and a key")
        if self.ai_summary_provider == "gemini" and self.ai_summary_model != "gemini-2.5-flash":
            raise ValueError("Gemini AI summaries require AI_SUMMARY_MODEL=gemini-2.5-flash")
        if self.embedding_provider not in {"fake", "openai", "gemini"}:
            raise ValueError("EMBEDDING_PROVIDER must be fake, openai, or gemini")
        if self.embedding_document_version != "semantic-discovery-v1":
            raise ValueError("EMBEDDING_DOCUMENT_VERSION must be semantic-discovery-v1")
        if self.embedding_dimension != 1536:
            raise ValueError("EMBEDDING_DIMENSION must match vector(1536)")
        if (
            self.embedding_provider == "openai"
            and self.semantic_search_enabled
            and (not self.embedding_real_provider_enabled or not self.openai_api_key)
        ):
            raise ValueError("OpenAI embeddings require real-provider enablement and a key")
        if (
            self.embedding_provider == "gemini"
            and self.semantic_search_enabled
            and (not self.embedding_real_provider_enabled or not self.gemini_api_key)
        ):
            raise ValueError("Gemini embeddings require real-provider enablement and a key")
        if self.embedding_provider == "gemini" and self.embedding_model != "gemini-embedding-001":
            raise ValueError("Gemini embeddings require EMBEDDING_MODEL=gemini-embedding-001")
        if self.environment == "production" and self.semantic_search_enabled:
            raise ValueError("Semantic Search requires the production durable worker rollout")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
