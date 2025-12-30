"""Multi-provider LLM factory with resilience patterns.

Provides production-grade LLM instantiation with:
- Auto-detection of available providers
- Circuit breaker protection for each provider
- Configurable retry and timeout settings
- Provider fallback when primary is unavailable
"""

from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.logging import get_logger
from app.core.resilience import CircuitBreakerOpenError, get_circuit_breaker

logger = get_logger(__name__)

# Provider priority for fallback (order matters)
PROVIDER_PRIORITY = ["anthropic", "openai", "google_genai"]

# Model defaults per provider (Dec 2025 - Latest Models)
# See SkillForge model_registry.py for full pricing/capabilities
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",  # $0.15/$0.60 - cost-effective, reliable
    "anthropic": "claude-sonnet-4-20250514",  # $3/$15 - SWE-bench leader (72.5%)
    "google_genai": "gemini-2.5-flash",  # $0.30/$2.50 - 1M context, fast
}


class LLMFactory:
    """Factory for creating LLM providers with resilience patterns.

    Features:
    - Auto-detection: Determines provider from available API keys
    - Circuit breaker: Protects against provider failures
    - Fallback: Tries alternative providers when primary fails
    - Retry: LangChain's built-in retry with configurable max_retries

    Usage:
        # Auto-detect provider
        llm = LLMFactory.create()

        # Specific provider
        llm = LLMFactory.create(provider="anthropic", model="claude-haiku-4-5-20251001")

        # With fallback on circuit breaker open
        llm = LLMFactory.create_with_fallback()
    """

    @classmethod
    def create(
        cls,
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Create an LLM instance for the specified provider.

        Args:
            provider: Provider name (openai, anthropic, google_genai).
                     If None, auto-detects from settings.
            model: Model name. If None, uses settings.LLM_MODEL or provider default.
            **kwargs: Additional arguments passed to the LLM constructor.

        Returns:
            Configured LLM instance.

        Raises:
            ValueError: If provider is not supported or API key is missing.
        """
        # Determine provider
        if provider is None:
            provider = settings.resolved_llm_provider()

        # Determine model
        if model is None:
            model = settings.LLM_MODEL or DEFAULT_MODELS.get(provider, "gpt-4o-mini")

        # Build kwargs with settings defaults
        final_kwargs = cls._build_kwargs(**kwargs)

        logger.info(
            "creating_llm",
            provider=provider,
            model=model,
            timeout=final_kwargs.get("timeout"),
            max_retries=final_kwargs.get("max_retries"),
        )

        return cls._create_for_provider(provider, model, **final_kwargs)

    @classmethod
    def create_with_fallback(
        cls,
        model: str | None = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Create LLM with automatic fallback to alternative providers.

        Tries providers in priority order, skipping those with:
        - Missing API keys
        - Open circuit breakers

        Args:
            model: Model name (will use provider default if not compatible)
            **kwargs: Additional arguments for LLM constructor

        Returns:
            LLM instance from first available provider

        Raises:
            RuntimeError: If all providers are unavailable
        """
        available_providers = cls.get_available_providers()

        for provider in available_providers:
            breaker = get_circuit_breaker(provider)

            if not breaker.is_closed:
                logger.info(
                    "skipping_provider_circuit_open",
                    provider=provider,
                )
                continue

            try:
                # Use provider-specific default model if none specified
                provider_model = model or DEFAULT_MODELS.get(provider)
                return cls.create(provider=provider, model=provider_model, **kwargs)
            except CircuitBreakerOpenError:
                logger.warning("provider_circuit_opened", provider=provider)
                continue
            except Exception as e:
                logger.warning(
                    "provider_creation_failed",
                    provider=provider,
                    error=str(e),
                )
                continue

        msg = "All LLM providers unavailable"
        raise RuntimeError(msg)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of providers with configured API keys.

        Returns:
            List of provider names in priority order
        """
        available = []
        for provider in PROVIDER_PRIORITY:
            if cls._has_api_key(provider):
                available.append(provider)
        return available

    @classmethod
    def _has_api_key(cls, provider: str) -> bool:
        """Check if provider has API key configured."""
        key_map = {
            "openai": settings.OPENAI_API_KEY,
            "anthropic": settings.ANTHROPIC_API_KEY,
            "google_genai": settings.GOOGLE_API_KEY,
        }
        return bool(key_map.get(provider))

    @classmethod
    def _build_kwargs(cls, **overrides: Any) -> dict[str, Any]:
        """Build kwargs with settings defaults and overrides."""
        defaults = {
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "timeout": settings.LLM_TIMEOUT,
            "max_retries": settings.LLM_MAX_RETRIES,
        }
        # Remove None values
        defaults = {k: v for k, v in defaults.items() if v is not None}
        # Apply overrides
        return {**defaults, **overrides}

    @classmethod
    def _create_for_provider(
        cls,
        provider: str,
        model: str,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Create LLM instance for specific provider."""
        creators = {
            "openai": cls._create_openai,
            "anthropic": cls._create_anthropic,
            "google_genai": cls._create_google,
        }

        creator = creators.get(provider)
        if creator is None:
            msg = f"Unsupported LLM provider: {provider}"
            raise ValueError(msg)

        return creator(model, **kwargs)

    @classmethod
    def _create_openai(cls, model: str, **kwargs: Any) -> BaseChatModel:
        """Create OpenAI LLM instance."""
        if not settings.OPENAI_API_KEY:
            msg = "OPENAI_API_KEY is required for OpenAI models"
            raise ValueError(msg)

        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            **kwargs,
        )

    @classmethod
    def _create_anthropic(cls, model: str, **kwargs: Any) -> BaseChatModel:
        """Create Anthropic LLM instance.

        Uses direct ChatAnthropic instantiation for prompt caching support.
        """
        if not settings.ANTHROPIC_API_KEY:
            msg = "ANTHROPIC_API_KEY is required for Anthropic models"
            raise ValueError(msg)

        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            **kwargs,
        )

    @classmethod
    def _create_google(cls, model: str, **kwargs: Any) -> BaseChatModel:
        """Create Google GenAI LLM instance."""
        if not settings.GOOGLE_API_KEY:
            msg = "GOOGLE_API_KEY is required for Google models"
            raise ValueError(msg)

        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            **kwargs,
        )


@lru_cache
def get_llm() -> BaseChatModel:
    """Get cached default LLM instance.

    Returns:
        Cached LLM instance using auto-detected provider
    """
    return LLMFactory.create()


def get_llm_with_fallback() -> BaseChatModel:
    """Get LLM with fallback to alternative providers.

    Unlike get_llm(), this is not cached to allow dynamic fallback.

    Returns:
        LLM instance from first available provider
    """
    return LLMFactory.create_with_fallback()
