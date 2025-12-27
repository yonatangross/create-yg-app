"""Resilience patterns for production-grade fault tolerance.

Implements circuit breaker pattern for LLM API calls to prevent
cascade failures when external services are unavailable.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Fast-fail, service unavailable
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 3  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: float = 60.0  # Time before attempting recovery
    excluded_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (ValueError, TypeError)
    )


class CircuitBreaker:
    """Async-safe circuit breaker for protecting external API calls.

    Usage:
        breaker = CircuitBreaker("openai")
        result = await breaker.call(async_fn, *args, **kwargs)

    Or as decorator:
        @circuit_breaker("anthropic")
        async def call_anthropic():
            ...
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Whether circuit allows requests."""
        return self._state == CircuitState.CLOSED

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from func if not handled
        """
        async with self._lock:
            await self._check_state()

            if self._state == CircuitState.OPEN:
                logger.warning(
                    "circuit_breaker_open",
                    name=self.name,
                    failures=self._failure_count,
                )
                raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            if not isinstance(e, self.config.excluded_exceptions):
                await self._on_failure(e)
            raise

    async def _check_state(self) -> None:
        """Check and potentially transition state based on timeout."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(
                    "circuit_breaker_half_open",
                    name=self.name,
                    elapsed_seconds=elapsed,
                )

    async def _on_success(self) -> None:
        """Handle successful execution."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("circuit_breaker_closed", name=self.name)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self, error: Exception) -> None:
        """Handle failed execution."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            logger.warning(
                "circuit_breaker_failure",
                name=self.name,
                failure_count=self._failure_count,
                error=str(error),
            )

            if self._state == CircuitState.HALF_OPEN:
                # Immediately open on half-open failure
                self._state = CircuitState.OPEN
                logger.warning("circuit_breaker_reopened", name=self.name)
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    threshold=self.config.failure_threshold,
                )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info("circuit_breaker_reset", name=self.name)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    pass


# Global circuit breakers for LLM providers
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    """Get or create circuit breaker for a provider.

    Args:
        provider: LLM provider name (openai, anthropic, google_genai)

    Returns:
        CircuitBreaker instance for the provider
    """
    if provider not in _breakers:
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60.0,
        )
        _breakers[provider] = CircuitBreaker(provider, config)
    return _breakers[provider]


def circuit_breaker(provider: str):
    """Decorator to protect async functions with circuit breaker.

    Args:
        provider: LLM provider name

    Usage:
        @circuit_breaker("openai")
        async def call_openai():
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_circuit_breaker(provider)
            return await breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
