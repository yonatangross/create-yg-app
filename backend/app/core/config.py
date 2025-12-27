"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Provider alias mapping for auto-detection
LLM_PROVIDER_ALIAS_MAP: Final[dict[str, str]] = {
    "openai": "openai",
    "gpt": "openai",
    "gpt4": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "sonnet": "anthropic",
    "google": "google_genai",
    "gemini": "google_genai",
    "google_genai": "google_genai",
}

LLM_PROVIDER_API_FIELDS: Final[dict[str, str]] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
}


def _infer_provider_from_model(model_identifier: str) -> str | None:
    """Infer provider from model identifier."""
    normalized = model_identifier.strip().lower()
    for alias, canonical in LLM_PROVIDER_ALIAS_MAP.items():
        if normalized.startswith(alias):
            return canonical
    return None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    API_V1_PREFIX: str = Field(default="/api/v1")

    # Server
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8600)

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:5183"])

    # Database
    DATABASE_URL: str | None = Field(default=None)

    # Redis Connection
    REDIS_URL: str = Field(default="redis://localhost:6390")
    REDIS_SOCKET_CONNECT_TIMEOUT: float = Field(default=5.0)
    REDIS_SOCKET_TIMEOUT: float = Field(default=5.0)
    REDIS_SOCKET_KEEPALIVE: bool = Field(default=True)
    REDIS_MAX_CONNECTIONS: int = Field(default=10)
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30)

    # Redis Caching (Semantic + Exact)
    REDIS_SEMANTIC_CACHE_TTL: int = Field(default=86400)  # 24 hours
    REDIS_SIMILARITY_THRESHOLD: float = Field(default=0.08)  # 92% similarity
    REDIS_EXACT_CACHE_TTL: int = Field(default=3600)  # 1 hour
    REDIS_CHAT_HISTORY_TTL: int = Field(default=604800)  # 7 days

    # LLM Configuration
    LLM_MODEL: str = Field(default="gpt-4o-mini")
    LLM_PROVIDER: str | None = Field(default=None)
    LLM_TEMPERATURE: float | None = Field(default=None)
    LLM_MAX_TOKENS: int | None = Field(default=None)
    LLM_TIMEOUT: float = Field(default=60.0)
    LLM_MAX_RETRIES: int = Field(default=3)

    # API Keys
    OPENAI_API_KEY: str | None = Field(default=None)
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    GOOGLE_API_KEY: str | None = Field(default=None)

    # Langfuse Observability
    LANGFUSE_ENABLED: bool = Field(default=False)
    LANGFUSE_HOST: str = Field(default="http://localhost:3010")
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None)
    LANGFUSE_SECRET_KEY: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            msg = f"ENVIRONMENT must be one of {allowed}"
            raise ValueError(msg)
        return v

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def resolved_llm_provider(self) -> str:
        """Return canonical provider name for the configured LLM."""
        if self.LLM_PROVIDER:
            normalized = self.LLM_PROVIDER.strip().lower()
            return LLM_PROVIDER_ALIAS_MAP.get(normalized, normalized)

        inferred = _infer_provider_from_model(self.LLM_MODEL)
        if inferred:
            return inferred

        # Auto-detect from available API keys
        if self.OPENAI_API_KEY:
            return "openai"
        if self.ANTHROPIC_API_KEY:
            return "anthropic"
        if self.GOOGLE_API_KEY:
            return "google_genai"

        msg = "Unable to determine LLM provider. Set LLM_PROVIDER or provide an API key."
        raise ValueError(msg)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
