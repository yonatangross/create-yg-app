"""Tests for admin API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.admin import verify_admin_key
from app.core.config import settings
from app.db.models.memory import MemoryType

# Set a test API key for consistent testing
TEST_ADMIN_KEY = "test-admin-key-for-unit-tests"


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_admin_api_key():
    """Auto-applied fixture to ensure ADMIN_API_KEY is set for all tests."""
    with patch.object(settings, "ADMIN_API_KEY", TEST_ADMIN_KEY):
        yield


# --- Auth Tests ---


@pytest.mark.asyncio
async def test_verify_admin_key_valid(mock_admin_api_key):
    """Test admin key verification with valid key."""
    # autouse fixture sets ADMIN_API_KEY to TEST_ADMIN_KEY
    await verify_admin_key(x_admin_key=TEST_ADMIN_KEY)


@pytest.mark.asyncio
async def test_verify_admin_key_invalid(mock_admin_api_key):
    """Test admin key verification with invalid key."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(x_admin_key="wrong-key")

    assert exc_info.value.status_code == 403
    assert "Invalid or missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_admin_key_missing(mock_admin_api_key):
    """Test admin key verification with missing key when key is configured."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(x_admin_key=None)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_admin_key_dev_mode_no_key():
    """Test admin key verification allows access in dev mode without key configured.

    Note: This test uses its own ADMIN_API_KEY patch to override the autouse fixture.
    """
    with patch.object(settings, "ADMIN_API_KEY", None):
        with patch.object(settings, "ENVIRONMENT", "development"):
            # Should not raise - dev mode allows access without key
            await verify_admin_key(x_admin_key=None)


@pytest.mark.asyncio
async def test_verify_admin_key_production_no_key_configured():
    """Test admin key verification fails in production without key configured.

    Note: This test uses its own ADMIN_API_KEY patch to override the autouse fixture.
    """
    with patch.object(settings, "ADMIN_API_KEY", None):
        with patch.object(settings, "ENVIRONMENT", "production"):
            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_key(x_admin_key=None)

            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail


# --- Memory Endpoints Tests (with mocked DB) ---


@pytest.fixture
def mock_db_session():
    """Create mock database session for testing."""
    mock_session = AsyncMock()
    # Default empty results
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    return mock_session


def test_list_memories_unauthorized(client):
    """Test list memories without auth."""
    response = client.get("/api/v1/admin/memories")
    assert response.status_code == 403


def test_list_memories_empty(client, mock_db_session):
    """Test list memories with valid auth."""
    with patch("app.api.v1.admin.get_db") as mock_get_db:
        # Setup mock to return session
        async def _get_db():
            yield mock_db_session

        mock_get_db.return_value = _get_db()

        # Override the dependency
        from app.db.session import get_db
        from app.main import app

        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            response = client.get(
                "/api/v1/admin/memories",
                headers={"X-Admin-Key": TEST_ADMIN_KEY},
            )
            assert response.status_code == 200
            data = response.json()
            assert "memories" in data
            assert "total" in data
            assert data["limit"] == 50
            assert data["offset"] == 0
        finally:
            app.dependency_overrides.clear()


def test_list_memories_with_pagination(client, mock_db_session):
    """Test list memories with pagination params."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.get(
            "/api/v1/admin/memories?limit=10&offset=5",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5
    finally:
        app.dependency_overrides.clear()


def test_list_memories_invalid_type(client, mock_db_session):
    """Test list memories with invalid memory type."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.get(
            "/api/v1/admin/memories?memory_type=invalid_type",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 400
        assert "Invalid memory_type" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_list_memories_with_filters(client, mock_db_session):
    """Test list memories with valid filters."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.get(
            f"/api/v1/admin/memories?memory_type={MemoryType.USER_PREFERENCE.value}&conversation_id=test123",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_get_memory_not_found(client, mock_db_session):
    """Test get memory with non-existent ID."""
    from app.db.session import get_db
    from app.main import app

    # Return None for scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        memory_id = uuid.uuid4()
        response = client.get(
            f"/api/v1/admin/memories/{memory_id}",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_memory_not_found(client, mock_db_session):
    """Test delete memory with non-existent ID."""
    from app.db.session import get_db
    from app.main import app

    # Return None for scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        memory_id = uuid.uuid4()
        response = client.delete(
            f"/api/v1/admin/memories/{memory_id}",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_clear_memories_no_filters(client, mock_db_session):
    """Test clear memories without any filters."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.delete(
            "/api/v1/admin/memories",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 400
        assert "At least one filter" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_clear_memories_with_conversation_id(client, mock_db_session):
    """Test clear memories with conversation_id filter."""
    from app.db.session import get_db
    from app.main import app

    # Mock rowcount for delete
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.delete(
            "/api/v1/admin/memories?conversation_id=test123",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert data["deleted_count"] >= 0
    finally:
        app.dependency_overrides.clear()


def test_clear_memories_with_type(client, mock_db_session):
    """Test clear memories with memory_type filter."""
    from app.db.session import get_db
    from app.main import app

    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.delete(
            f"/api/v1/admin/memories?memory_type={MemoryType.LEARNED_FACT.value}",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_clear_memories_with_older_than(client, mock_db_session):
    """Test clear memories with older_than_days filter."""
    from app.db.session import get_db
    from app.main import app

    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.delete(
            "/api/v1/admin/memories?older_than_days=30",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_clear_memories_invalid_type(client, mock_db_session):
    """Test clear memories with invalid memory type."""
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.delete(
            "/api/v1/admin/memories?memory_type=invalid",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_memory_stats(client, mock_db_session):
    """Test memory statistics endpoint."""
    from app.db.session import get_db
    from app.main import app

    # Mock different returns for different queries using side_effect
    call_count = [0]

    async def mock_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:  # Total count
            result.scalar.return_value = 10
        elif call_count[0] == 2:  # By type
            result.__iter__ = lambda self: iter([])
        elif call_count[0] == 3 or call_count[0] == 4:  # Oldest
            result.scalar.return_value = None
        return result

    mock_db_session.execute = mock_execute

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.get(
            "/api/v1/admin/memories/stats",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_memories" in data
        assert "by_type" in data
        assert "oldest_memory" in data
        assert "newest_memory" in data
    finally:
        app.dependency_overrides.clear()


# --- Cache Endpoints Tests ---


@pytest.mark.asyncio
async def test_cache_stats_unauthorized(client):
    """Test cache stats without auth."""
    response = client.get("/api/v1/admin/cache/stats")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cache_stats_success(client):
    """Test cache stats with valid auth."""
    with patch("app.api.v1.admin.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.dbsize.return_value = 100
        mock_client.info.return_value = {
            "used_memory": 1024 * 1024,  # 1 MB
            "redis_version": "7.0.0",
            "uptime_in_seconds": 3600,
        }
        mock_get_client.return_value = mock_client

        response = client.get(
            "/api/v1/admin/cache/stats",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_keys"] == 100
        assert data["memory_usage_mb"] == 1.0
        assert data["redis_version"] == "7.0.0"
        assert data["uptime_seconds"] == 3600


@pytest.mark.asyncio
async def test_clear_cache_all(client):
    """Test clearing all cache."""
    with patch("app.api.v1.admin.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.flushdb.return_value = None
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/admin/cache/clear",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == -1  # Unknown count for flushdb


@pytest.mark.asyncio
async def test_clear_cache_with_prefix(client):
    """Test clearing cache with prefix."""
    with patch("app.api.v1.admin.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()

        # Mock scan_iter to return some keys
        async def mock_scan_iter(*args, **kwargs):
            for key in ["embed:key1", "embed:key2"]:
                yield key

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete.return_value = 2
        mock_get_client.return_value = mock_client

        response = client.post(
            "/api/v1/admin/cache/clear?prefix=embed:",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2


@pytest.mark.asyncio
async def test_embedding_cache_stats(client):
    """Test embedding cache statistics."""
    with patch("app.api.v1.admin.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()

        # Mock scan_iter for different patterns
        async def mock_scan_iter(match=None, count=100):
            if match == "embed:*":
                for _ in range(50):
                    yield "embed:key"
            elif match == "yg-starter:chat:*":
                for _ in range(20):
                    yield "chat:key"
            elif match == "semantic:*":
                for _ in range(10):
                    yield "semantic:key"

        mock_client.scan_iter = mock_scan_iter
        mock_get_client.return_value = mock_client

        response = client.get(
            "/api/v1/admin/cache/embedding-stats",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["embedding_cache_keys"] == 50
        assert data["chat_history_keys"] == 20
        assert data["semantic_cache_keys"] == 10
        assert data["total_tracked"] == 80


# --- System Info Tests ---


def test_system_info_unauthorized(client):
    """Test system info without auth."""
    response = client.get("/api/v1/admin/info")
    assert response.status_code == 403


def test_system_info_success(client):
    """Test system info with valid auth."""
    response = client.get(
        "/api/v1/admin/info",
        headers={"X-Admin-Key": TEST_ADMIN_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"
    assert data["environment"] == settings.ENVIRONMENT
    assert "uptime_seconds" in data
    assert "config" in data
    assert "llm_model" in data["config"]
    assert "llm_provider" in data["config"]


# --- Usage Stats Tests ---


def test_usage_stats_unauthorized(client):
    """Test usage stats without auth."""
    response = client.get("/api/v1/admin/stats/usage")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_usage_stats_success(client):
    """Test usage stats with valid auth."""
    with patch("app.api.v1.admin.get_usage_stats") as mock_get_stats:
        mock_stats = AsyncMock()
        mock_stats.get_stats.return_value = {
            "chats": {"total": 100, "today": 10},
            "tokens": {"input": 50000, "output": 25000},
            "embeddings": {"total": 500, "cached": 400},
        }
        mock_get_stats.return_value = mock_stats

        response = client.get(
            "/api/v1/admin/stats/usage",
            headers={"X-Admin-Key": TEST_ADMIN_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert "chats" in data
        assert "tokens" in data


# --- Integration Test with Database ---


@pytest.mark.asyncio
async def test_memory_crud_flow(async_client):
    """Test complete CRUD flow for memories."""
    # This test would require a test database setup
    # Keeping it as a placeholder for integration tests

    # 1. Create a memory (via MemoryService, not admin API)
    # 2. List memories and verify it's there
    # 3. Get specific memory by ID
    # 4. Delete memory
    # 5. Verify it's gone
    pass


@pytest.mark.asyncio
async def test_memory_stats_with_data(async_client):
    """Test memory stats with actual data."""
    # This test would require a test database with sample data
    pass
