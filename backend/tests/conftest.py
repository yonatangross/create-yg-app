"""Pytest fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def settings():
    """Get test settings."""
    get_settings.cache_clear()
    return get_settings()


class MockLLM:
    """Deterministic mock LLM for testing.

    Provides predictable responses without calling real APIs.
    """

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.calls: list[dict] = []

    async def ainvoke(self, messages, **kwargs):
        """Mock async invoke."""
        self.calls.append({"messages": messages, "kwargs": kwargs})
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        # Return mock AIMessage-like object
        return MagicMock(content=response)

    def invoke(self, messages, **kwargs):
        """Mock sync invoke."""
        self.calls.append({"messages": messages, "kwargs": kwargs})
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MagicMock(content=response)


@pytest.fixture
def mock_llm():
    """Create mock LLM instance."""
    return MockLLM()


@pytest.fixture
def mock_llm_factory(mock_llm, monkeypatch):
    """Patch LLM factory to return mock LLM."""
    from app.llm import factory

    monkeypatch.setattr(factory, "get_llm", lambda: mock_llm)
    return mock_llm
