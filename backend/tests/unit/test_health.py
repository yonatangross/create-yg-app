"""Tests for health endpoints."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_check(client):
    """Test readiness check endpoint with mocked dependencies."""
    # Mock database session
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with (
        patch("app.api.v1.health.get_session", mock_get_session),
        patch("redis.asyncio.from_url") as mock_redis_from_url,
    ):
        mock_redis_from_url.return_value = mock_redis

        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is True


def test_readiness_check_db_failure(client):
    """Test readiness check when database is unavailable."""

    # Mock database session to raise exception
    @asynccontextmanager
    async def mock_get_session_fail():
        raise Exception("DB connection failed")
        yield  # noqa: RET505

    # Mock Redis (still works)
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with (
        patch("app.api.v1.health.get_session", mock_get_session_fail),
        patch("redis.asyncio.from_url") as mock_redis_from_url,
    ):
        mock_redis_from_url.return_value = mock_redis

        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is False
        assert data["checks"]["redis"] is True


def test_readiness_check_redis_failure(client):
    """Test readiness check when Redis is unavailable."""
    # Mock database session (works)
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    # Mock Redis to raise exception
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = Exception("Redis connection failed")

    with (
        patch("app.api.v1.health.get_session", mock_get_session),
        patch("redis.asyncio.from_url") as mock_redis_from_url,
    ):
        mock_redis_from_url.return_value = mock_redis

        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is False
