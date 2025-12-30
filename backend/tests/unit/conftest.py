"""Unit test configuration with autouse fixtures for isolation.

All unit tests should be fully isolated with no real I/O.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_asyncio_sleep():
    """Automatically mock asyncio.sleep in all unit tests.

    This ensures unit tests are fast and don't have real delays.
    """
    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
def mock_time_sleep():
    """Automatically mock time.sleep in all unit tests."""
    with patch("time.sleep"):
        yield


@pytest.fixture(autouse=True)
def prevent_real_redis_connections():
    """Prevent accidental real Redis connections in unit tests.

    Tests that need Redis should explicitly provide mock_redis fixture.
    """

    def raise_redis_error(*args, **kwargs):
        raise RuntimeError(
            "Real Redis connection attempted in unit test! Use mock_redis fixture instead."
        )

    with (
        patch("redis.asyncio.from_url", side_effect=raise_redis_error),
        patch("redis.Redis", side_effect=raise_redis_error),
    ):
        yield


@pytest.fixture(autouse=True)
def prevent_real_http_requests(monkeypatch):
    """Prevent real HTTP requests in unit tests.

    Tests that need HTTP should use httpx.AsyncClient with transport mocks.
    """
    import httpx

    async def raise_http_error(*args, **kwargs):
        raise RuntimeError(
            "Real HTTP request attempted in unit test! "
            "Use httpx mock transport or pytest-httpx instead."
        )

    # Prevent real requests via httpx
    monkeypatch.setattr(httpx.AsyncClient, "request", raise_http_error)
