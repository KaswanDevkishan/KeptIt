from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://user:password@db.example/keptit?sslmode=require",
        "cors_origins": ["https://keptit-ui.onrender.com"],
        "frontend_password_reset_url": "https://keptit-ui.onrender.com/reset-password",
        "session_cookie_secure": True,
        "session_cookie_samesite": "none",
        "email_backend": "disabled",
        "spaces_cursor_secret": "a-production-secret-with-enough-entropy",
    }
    values.update(overrides)
    return Settings(_env_file=None, **cast(dict[str, Any], values))


def test_local_defaults_remain_valid() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert not settings.session_cookie_secure


@pytest.mark.parametrize(
    "override",
    [
        {"session_cookie_secure": False},
        {"session_cookie_samesite": "strict"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["http://frontend.example.com"]},
        {"cors_origins": ["https://localhost:5173"]},
        {"email_backend": "development_file"},
    ],
)
def test_production_rejects_unsafe_web_configuration(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        production_settings(**override)


def test_disabled_optional_ai_needs_no_key() -> None:
    settings = production_settings()
    assert not settings.ai_summaries_enabled
    assert not settings.semantic_search_enabled


def test_same_site_production_cookie_configuration_is_valid() -> None:
    settings = production_settings(
        cors_origins=["https://app.keptit.example"],
        frontend_password_reset_url="https://app.keptit.example/reset-password",
        session_cookie_samesite="lax",
    )

    assert settings.session_cookie_secure
    assert settings.session_cookie_samesite == "lax"


def test_enabled_gemini_requires_real_provider_and_key() -> None:
    with pytest.raises(ValidationError, match="Gemini embeddings"):
        production_settings(
            environment="staging",
            semantic_search_enabled=True,
            embedding_provider="gemini",
            embedding_model="gemini-embedding-001",
        )

    settings = Settings(
        _env_file=None,
        environment="staging",
        semantic_search_enabled=True,
        embedding_real_provider_enabled=True,
        embedding_provider="gemini",
        embedding_model="gemini-embedding-001",
        gemini_api_key="test-key",
    )
    assert settings.gemini_api_key == "test-key"
