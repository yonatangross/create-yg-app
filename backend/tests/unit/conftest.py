"""Unit test configuration with autouse fixtures for isolation.

All unit tests should be fully isolated with no real I/O.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Mock required environment variables for unit tests.

    This ensures unit tests don't fail due to missing config.
    """
    from app.core.config import get_settings

    # Clear settings cache to pick up mocked env vars
    get_settings.cache_clear()

    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379",
        "OPENAI_API_KEY": "sk-test-fake-key-for-unit-tests",
        "ENVIRONMENT": "test",
    }
    with patch.dict(os.environ, env_vars):
        # Clear again after patching to ensure fresh settings
        get_settings.cache_clear()
        yield
        # Clear after test to not affect other tests
        get_settings.cache_clear()


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


@pytest.fixture(autouse=True)
def prevent_real_database_connections():
    """Prevent accidental real database connections in unit tests.

    Tests that need database should explicitly provide mock_db_session fixture.
    """
    from unittest.mock import MagicMock

    # Create a mock engine that doesn't connect
    mock_engine = MagicMock()

    with patch("app.db.session.get_engine", return_value=mock_engine):
        yield
