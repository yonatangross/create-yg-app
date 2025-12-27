"""Unified Langfuse Service - Single Source of Truth for Langfuse Integration.

This module provides a comprehensive Langfuse service that combines:
1. Langfuse Python SDK for core observability (tracing, scoring, prompts)
2. Additional API methods for annotation queues and datasets
3. Graceful degradation when Langfuse is unavailable
4. Singleton pattern for application-wide access

Usage:
    >>> from app.core.langfuse_service import get_langfuse_service
    >>> service = get_langfuse_service()
    >>> if service:
    ...     service.submit_score(name="relevance", value=0.9)

"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class LangfuseServiceError(Exception):
    """Base exception for Langfuse service errors."""


class LangfuseUnavailableError(LangfuseServiceError):
    """Raised when Langfuse is unavailable after retries."""


# ============================================================================
# Unified Langfuse Service
# ============================================================================


class LangfuseService:
    """Unified service for all Langfuse operations.

    This service provides a single interface for:
    - SDK-based operations (traces, scores, prompts via Python SDK)
    - REST API operations (annotation queues, datasets via HTTP)
    - LangChain callback handler integration
    - Graceful degradation when Langfuse is unavailable

    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "http://localhost:3000",
        *,
        release: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Langfuse service."""
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host.rstrip("/")
        self.release = release
        self.timeout = timeout
        self.max_retries = max_retries

        self._sdk_client: Any = None
        self._http_client: httpx.AsyncClient | None = None

        self._initialize_sdk()

        logger.info(
            "langfuse_service_initialized",
            host=self.host,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def _initialize_sdk(self) -> None:
        """Initialize the Langfuse Python SDK client."""
        try:
            from langfuse import Langfuse

            self._sdk_client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
                release=self.release,
                tracing_enabled=True,
            )

            logger.info(
                "langfuse_sdk_initialized",
                message="Langfuse SDK client configured successfully",
                host=self.host,
            )

        except ImportError:
            logger.warning(
                "langfuse_sdk_import_failed",
                message="Langfuse package not installed, run: uv add langfuse",
            )
            self._sdk_client = None
        except Exception as e:
            logger.error(
                "langfuse_sdk_initialization_failed",
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            self._sdk_client = None

    @classmethod
    def from_env(cls) -> LangfuseService | None:
        """Create service from environment variables."""
        langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        if not langfuse_enabled:
            logger.debug("langfuse_disabled", message="LANGFUSE_ENABLED is not true")
            return None

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")

        if not public_key or not secret_key:
            logger.warning(
                "langfuse_credentials_missing",
                public_key_set=bool(public_key),
                secret_key_set=bool(secret_key),
            )
            return None

        return cls(
            public_key=public_key,
            secret_key=secret_key,
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
            release=os.getenv("LANGFUSE_RELEASE"),
            timeout=float(os.getenv("LANGFUSE_TIMEOUT", "30")),
            max_retries=int(os.getenv("LANGFUSE_MAX_RETRIES", "3")),
        )

    @property
    def sdk_client(self) -> Any:
        """Get the Langfuse Python SDK client."""
        return self._sdk_client

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                auth=(self.public_key, self.secret_key),
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Content-Type": "application/json",
                    "X-Langfuse-SDK-Name": "yg-starter-langfuse-service",
                    "X-Langfuse-SDK-Version": "1.0.0",
                },
            )
        return self._http_client

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
            reraise=True,
        )
        async def _make_request() -> dict[str, Any]:
            client = await self._get_http_client()
            url = f"{self.host}{endpoint}"

            start_time = time.monotonic()

            response = await client.request(
                method=method,
                url=url,
                json=json,
                params=params,
            )

            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "langfuse_api_request",
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                elapsed_ms=round(elapsed_ms, 2),
            )

            response.raise_for_status()
            return response.json() if response.content else {}

        try:
            return await _make_request()
        except RetryError as e:
            logger.exception(
                "langfuse_request_failed",
                method=method,
                endpoint=endpoint,
                retries=self.max_retries,
            )
            msg = f"Langfuse unavailable after {self.max_retries} retries"
            raise LangfuseUnavailableError(msg) from e
        except httpx.HTTPStatusError as e:
            logger.exception(
                "langfuse_http_error",
                method=method,
                endpoint=endpoint,
                status_code=e.response.status_code,
            )
            msg = f"Langfuse API error: {e.response.status_code}"
            raise LangfuseServiceError(msg) from e

    def flush(self) -> None:
        """Flush pending Langfuse events."""
        if self._sdk_client is not None:
            try:
                self._sdk_client.flush()
                logger.debug("langfuse_flushed", message="Langfuse events flushed")
            except Exception as e:
                logger.error(
                    "langfuse_flush_failed",
                    error=str(e),
                    exc_info=True,
                )

    async def shutdown(self) -> None:
        """Shutdown Langfuse service gracefully."""
        if self._sdk_client is not None:
            try:
                self._sdk_client.flush()
                self._sdk_client.shutdown()
                logger.info("langfuse_sdk_shutdown", message="Langfuse SDK client shutdown")
            except Exception as e:
                logger.error(
                    "langfuse_sdk_shutdown_failed",
                    error=str(e),
                    exc_info=True,
                )

        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

        logger.info("langfuse_service_shutdown", message="Langfuse service shutdown complete")

    def submit_score(
        self,
        *,
        trace_id: str | None = None,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """Submit a score to Langfuse for quality tracking."""
        if self._sdk_client is None:
            logger.debug("langfuse_score_skipped_no_sdk", message="Langfuse SDK not available")
            return

        try:
            if trace_id is None:
                trace_id = self._sdk_client.get_current_trace_id()

            if trace_id is None:
                logger.debug(
                    "langfuse_score_skipped_no_trace",
                    message="No trace context available for score submission",
                    score_name=name,
                )
                return

            self._sdk_client.create_score(
                trace_id=str(trace_id),
                name=name,
                value=value,
                comment=comment,
            )
            self._sdk_client.flush()

            logger.debug(
                "langfuse_score_submitted",
                trace_id=str(trace_id),
                score_name=name,
                score_value=value,
            )

        except Exception as e:
            logger.warning(
                "langfuse_score_failed",
                error=str(e),
                score_name=name,
                exc_info=True,
            )

    def get_callback_handler(self) -> Any:
        """Get Langfuse CallbackHandler for LangChain integration."""
        try:
            from langfuse.langchain import CallbackHandler

            handler = CallbackHandler()

            logger.debug(
                "langfuse_callback_created",
                message="Langfuse CallbackHandler created for LangChain integration",
            )

            return handler

        except ImportError:
            logger.warning(
                "langfuse_callback_import_failed",
                message="langfuse.langchain not available - install langfuse[langchain]",
            )
            return None
        except Exception:
            logger.exception("langfuse_callback_failed")
            return None

    async def get_prompt(
        self,
        name: str,
        *,
        version: int | None = None,
        label: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a prompt from Langfuse."""
        params: dict[str, Any] = {"name": name}
        if version is not None:
            params["version"] = version
        if label:
            params["label"] = label

        try:
            result = await self._request("GET", "/api/public/v2/prompts", params=params)
            logger.info(
                "langfuse_prompt_fetched",
                prompt_name=name,
                version=version,
                label=label,
            )
            return result
        except LangfuseServiceError:
            logger.warning(
                "langfuse_prompt_not_found",
                prompt_name=name,
                version=version,
                label=label,
            )
            return None


# ============================================================================
# Module-Level Singleton and Helper Functions
# ============================================================================

_langfuse_service: LangfuseService | None = None


def get_langfuse_service() -> LangfuseService | None:
    """Get or create Langfuse service singleton."""
    global _langfuse_service  # noqa: PLW0603 - Module-level singleton pattern

    if _langfuse_service is None:
        _langfuse_service = LangfuseService.from_env()

    return _langfuse_service


def configure_langfuse_service() -> None:
    """Configure Langfuse service on application startup."""
    service = get_langfuse_service()
    if service:
        logger.info(
            "langfuse_startup_complete",
            message="Langfuse observability ready",
        )


async def shutdown_langfuse_service() -> None:
    """Shutdown Langfuse service gracefully."""
    global _langfuse_service  # noqa: PLW0603

    if _langfuse_service is not None:
        await _langfuse_service.shutdown()
        _langfuse_service = None
