import hashlib
import math
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai import OpenAI

from app.core.config import Settings


class EmbeddingProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    usage_tokens: int | None = None


class EmbeddingProvider(Protocol):
    provider: str
    model: str
    dimension: int

    def embed_one(
        self, text: str, purpose: Literal["document", "query"], timeout: float
    ) -> EmbeddingResult: ...

    def embed_batch(
        self, texts: list[str], purpose: Literal["document"], timeout: float
    ) -> list[EmbeddingResult]: ...


def validate_vector(vector: list[float], dimension: int) -> None:
    if len(vector) != dimension or any(not math.isfinite(value) for value in vector):
        raise EmbeddingProviderError(
            "invalid_output", "The embedding provider returned invalid output."
        )
    if math.sqrt(sum(value * value for value in vector)) == 0:
        raise EmbeddingProviderError(
            "invalid_output", "The embedding provider returned invalid output."
        )


class FakeEmbeddingProvider:
    provider = "fake"

    def __init__(self, model: str, dimension: int, behavior: str = "success") -> None:
        self.model, self.dimension, self.behavior = model, dimension, behavior

    def embed_one(
        self, text: str, purpose: Literal["document", "query"], timeout: float
    ) -> EmbeddingResult:
        del purpose, timeout
        errors = {
            "timeout": ("timeout", "The embedding provider timed out."),
            "rate_limit": ("rate_limited", "The embedding provider is busy."),
            "unavailable": ("unavailable", "The embedding provider is unavailable."),
            "unsupported": ("unsupported_input", "This content cannot be embedded."),
        }
        if self.behavior in errors:
            raise EmbeddingProviderError(*errors[self.behavior])
        dimension = self.dimension - 1 if self.behavior == "malformed_dimension" else self.dimension
        values = []
        for index in range(dimension):
            digest = hashlib.sha256(f"{index}\0{text}".encode()).digest()
            values.append((int.from_bytes(digest[:8], "big") / (2**64 - 1)) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in values))
        vector = [value / norm for value in values]
        validate_vector(vector, self.dimension)
        return EmbeddingResult(vector=vector, usage_tokens=max(1, len(text) // 4))

    def embed_batch(
        self, texts: list[str], purpose: Literal["document"], timeout: float
    ) -> list[EmbeddingResult]:
        return [self.embed_one(text, purpose, timeout) for text in texts]


class OpenAIEmbeddingProvider:
    provider = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.embedding_real_provider_enabled or not settings.openai_api_key:
            raise EmbeddingProviderError("not_configured", "Embedding provider is not configured.")
        self.model, self.dimension = settings.embedding_model, settings.embedding_dimension
        self.client = OpenAI(
            api_key=settings.openai_api_key, timeout=settings.embedding_timeout_seconds
        )

    def embed_one(
        self, text: str, purpose: Literal["document", "query"], timeout: float
    ) -> EmbeddingResult:
        del purpose
        try:
            response = self.client.embeddings.create(
                model=self.model, input=text, dimensions=self.dimension, timeout=timeout
            )
            vector = list(response.data[0].embedding)
            validate_vector(vector, self.dimension)
            return EmbeddingResult(vector, getattr(response.usage, "prompt_tokens", None))
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            name = type(exc).__name__.lower()
            code = (
                "timeout"
                if "timeout" in name
                else "rate_limited"
                if "rate" in name
                else "unavailable"
            )
            raise EmbeddingProviderError(
                code, "The embedding provider is temporarily unavailable."
            ) from exc

    def embed_batch(
        self, texts: list[str], purpose: Literal["document"], timeout: float
    ) -> list[EmbeddingResult]:
        return [self.embed_one(text, purpose, timeout) for text in texts]


class GeminiEmbeddingProvider:
    provider = "gemini"
    supported_model = "gemini-embedding-001"
    supported_dimension = 1536

    def __init__(self, settings: Settings) -> None:
        if not settings.embedding_real_provider_enabled:
            raise EmbeddingProviderError("not_configured", "Embedding provider is not configured.")
        if not settings.gemini_api_key:
            raise EmbeddingProviderError("not_configured", "Embedding provider is not configured.")
        if (
            settings.embedding_model != self.supported_model
            or settings.embedding_dimension != self.supported_dimension
        ):
            raise EmbeddingProviderError(
                "unsupported_configuration", "Embedding provider configuration is unsupported."
            )
        self.model, self.dimension = settings.embedding_model, settings.embedding_dimension
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def embed_one(
        self, text: str, purpose: Literal["document", "query"], timeout: float
    ) -> EmbeddingResult:
        task_type = "RETRIEVAL_DOCUMENT" if purpose == "document" else "RETRIEVAL_QUERY"
        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=genai_types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimension,
                    http_options=genai_types.HttpOptions(timeout=int(timeout * 1000)),
                ),
            )
            try:
                embeddings = response.embeddings
                if not embeddings or len(embeddings) != 1 or embeddings[0].values is None:
                    raise ValueError
                vector = [float(value) for value in embeddings[0].values]
            except (AttributeError, IndexError, TypeError, ValueError) as exc:
                raise EmbeddingProviderError(
                    "invalid_output", "The embedding provider returned invalid output."
                ) from exc
            validate_vector(vector, self.dimension)
            return EmbeddingResult(vector=vector, usage_tokens=None)
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise _classify_gemini_error(exc) from exc

    def embed_batch(
        self, texts: list[str], purpose: Literal["document"], timeout: float
    ) -> list[EmbeddingResult]:
        return [self.embed_one(text, purpose, timeout) for text in texts]


def _classify_gemini_error(exc: Exception) -> EmbeddingProviderError:
    status = getattr(exc, "code", None)
    name = type(exc).__name__.lower()
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)) or "timeout" in name:
        code = "timeout"
    elif status in {400, 401, 403}:
        code = "invalid_credentials" if status in {400, 401} else "permission_denied"
    elif status == 429:
        code = "rate_limited"
    elif status in {500, 502, 503, 504}:
        code = "unavailable"
    elif isinstance(exc, httpx.NetworkError):
        code = "network_failure"
    elif isinstance(exc, genai_errors.APIError):
        code = "unknown_provider_failure"
    else:
        code = (
            "network_failure"
            if "connect" in name or "network" in name
            else "unknown_provider_failure"
        )
    return EmbeddingProviderError(code, "The embedding provider is temporarily unavailable.")


def get_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(
            settings.embedding_model, settings.embedding_dimension, settings.embedding_fake_behavior
        )
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    return GeminiEmbeddingProvider(settings)
