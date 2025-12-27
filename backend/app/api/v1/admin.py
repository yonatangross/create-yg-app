"""Admin API endpoints for managing memories and cache."""

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.memory import AgentMemory, MemoryType
from app.db.session import get_db
from app.shared.services.stats.usage_stats import get_usage_stats

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Auth Dependency ---


async def verify_admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    """Verify admin API key from X-Admin-Key header.

    Args:
        x_admin_key: API key from request header

    Raises:
        HTTPException: 403 if key is missing or invalid
    """
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        logger.warning("admin_auth_failed", provided_key=bool(x_admin_key))
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing admin API key",
        )


# --- Response Models ---


class MemoryResponse(BaseModel):
    """Single memory response."""

    id: uuid.UUID
    memory_type: str
    content: str
    conversation_id: str | None
    relevance_score: float
    memory_metadata: dict
    created_at: datetime
    last_accessed_at: datetime | None


class MemoryListResponse(BaseModel):
    """List of memories with pagination."""

    memories: list[MemoryResponse]
    total: int
    limit: int
    offset: int


class MemoryStatsResponse(BaseModel):
    """Memory statistics."""

    total_memories: int
    by_type: dict[str, int]
    oldest_memory: datetime | None
    newest_memory: datetime | None


class CacheStatsResponse(BaseModel):
    """Cache statistics."""

    total_keys: int
    memory_usage_mb: float | None
    redis_version: str | None
    uptime_seconds: int | None


class DeleteResponse(BaseModel):
    """Delete operation response."""

    deleted_count: int
    message: str


class SystemInfoResponse(BaseModel):
    """System information."""

    version: str
    environment: str
    uptime_seconds: float
    config: dict


# --- Memory Management Endpoints ---


@router.get("/memories/stats", response_model=MemoryStatsResponse)
async def memory_stats(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_admin_key),
) -> MemoryStatsResponse:
    """Get memory statistics.

    Args:
        db: Database session
        _auth: Admin authentication

    Returns:
        MemoryStatsResponse with statistics
    """
    logger.info("admin_memory_stats")

    # Total count
    total_stmt = select(func.count()).select_from(AgentMemory)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Count by type
    type_stmt = select(
        AgentMemory.memory_type,
        func.count(AgentMemory.id).label("cnt"),
    ).group_by(AgentMemory.memory_type)
    type_result = await db.execute(type_stmt)
    by_type: dict[str, int] = {str(row.memory_type): int(row.cnt) for row in type_result}

    # Oldest and newest
    oldest_stmt = select(func.min(AgentMemory.created_at))
    oldest_result = await db.execute(oldest_stmt)
    oldest = oldest_result.scalar()

    newest_stmt = select(func.max(AgentMemory.created_at))
    newest_result = await db.execute(newest_stmt)
    newest = newest_result.scalar()

    return MemoryStatsResponse(
        total_memories=total,
        by_type=by_type,
        oldest_memory=oldest,
        newest_memory=newest,
    )


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    memory_type: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_admin_key),
) -> MemoryListResponse:
    """List all memories with pagination and filtering.

    Args:
        limit: Maximum number of memories to return (1-500)
        offset: Number of memories to skip
        memory_type: Filter by memory type
        conversation_id: Filter by conversation ID
        db: Database session
        _auth: Admin authentication

    Returns:
        MemoryListResponse with memories and pagination info
    """
    logger.info(
        "admin_list_memories",
        limit=limit,
        offset=offset,
        memory_type=memory_type,
        conversation_id=conversation_id,
    )

    # Build query
    stmt = select(AgentMemory).order_by(AgentMemory.created_at.desc())

    if memory_type:
        try:
            # Validate memory type
            MemoryType(memory_type)
            stmt = stmt.where(AgentMemory.memory_type == memory_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memory_type. Must be one of: {[t.value for t in MemoryType]}",
            ) from e

    if conversation_id:
        stmt = stmt.where(AgentMemory.conversation_id == conversation_id)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Get paginated results
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return MemoryListResponse(
        memories=[
            MemoryResponse(
                id=m.id,
                memory_type=m.memory_type,
                content=m.content,
                conversation_id=m.conversation_id,
                relevance_score=m.relevance_score,
                memory_metadata=m.memory_metadata,
                created_at=m.created_at,
                last_accessed_at=m.last_accessed_at,
            )
            for m in memories
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_admin_key),
) -> MemoryResponse:
    """Get a specific memory by ID.

    Args:
        memory_id: UUID of the memory to retrieve
        db: Database session
        _auth: Admin authentication

    Returns:
        MemoryResponse with memory details

    Raises:
        HTTPException: 404 if memory not found
    """
    logger.info("admin_get_memory", memory_id=str(memory_id))

    stmt = select(AgentMemory).where(AgentMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(
            status_code=404,
            detail=f"Memory {memory_id} not found",
        )

    return MemoryResponse(
        id=memory.id,
        memory_type=memory.memory_type,
        content=memory.content,
        conversation_id=memory.conversation_id,
        relevance_score=memory.relevance_score,
        memory_metadata=memory.memory_metadata,
        created_at=memory.created_at,
        last_accessed_at=memory.last_accessed_at,
    )


@router.delete("/memories/{memory_id}", response_model=DeleteResponse)
async def delete_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_admin_key),
) -> DeleteResponse:
    """Delete a specific memory.

    Args:
        memory_id: UUID of the memory to delete
        db: Database session
        _auth: Admin authentication

    Returns:
        DeleteResponse with deletion status

    Raises:
        HTTPException: 404 if memory not found
    """
    logger.info("admin_delete_memory", memory_id=str(memory_id))

    stmt = select(AgentMemory).where(AgentMemory.id == memory_id)
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(
            status_code=404,
            detail=f"Memory {memory_id} not found",
        )

    await db.delete(memory)
    await db.commit()

    logger.info("admin_memory_deleted", memory_id=str(memory_id))

    return DeleteResponse(
        deleted_count=1,
        message=f"Memory {memory_id} deleted successfully",
    )


@router.delete("/memories", response_model=DeleteResponse)
async def clear_memories(
    conversation_id: str | None = Query(default=None),
    memory_type: str | None = Query(default=None),
    older_than_days: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_admin_key),
) -> DeleteResponse:
    """Bulk delete memories with filters.

    At least one filter must be provided to prevent accidental deletion of all memories.

    Args:
        conversation_id: Delete memories for specific conversation
        memory_type: Delete memories of specific type
        older_than_days: Delete memories older than N days
        db: Database session
        _auth: Admin authentication

    Returns:
        DeleteResponse with number of deleted memories

    Raises:
        HTTPException: 400 if no filters provided
    """
    if not conversation_id and not memory_type and not older_than_days:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one filter (conversation_id, memory_type, older_than_days) is required"
            ),
        )

    logger.info(
        "admin_clear_memories",
        conversation_id=conversation_id,
        memory_type=memory_type,
        older_than_days=older_than_days,
    )

    # Build delete query
    stmt = delete(AgentMemory)

    if conversation_id:
        stmt = stmt.where(AgentMemory.conversation_id == conversation_id)

    if memory_type:
        try:
            MemoryType(memory_type)
            stmt = stmt.where(AgentMemory.memory_type == memory_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memory_type. Must be one of: {[t.value for t in MemoryType]}",
            ) from e

    if older_than_days:
        cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)
        stmt = stmt.where(AgentMemory.created_at < cutoff_date)

    # Execute deletion
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = getattr(result, "rowcount", 0) or 0

    logger.info("admin_memories_cleared", deleted_count=deleted_count)

    return DeleteResponse(
        deleted_count=deleted_count,
        message=f"Deleted {deleted_count} memories",
    )


# --- Cache Management Endpoints ---


async def get_redis_client() -> redis.Redis:
    """Get Redis client for admin operations.

    Returns:
        Redis client instance
    """
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def cache_stats(
    _auth: None = Depends(verify_admin_key),
) -> CacheStatsResponse:
    """Get cache statistics.

    Args:
        _auth: Admin authentication

    Returns:
        CacheStatsResponse with cache statistics
    """
    logger.info("admin_cache_stats")

    client = await get_redis_client()

    try:
        # Get database size (number of keys)
        db_size = await client.dbsize()

        # Get Redis info
        info = await client.info()

        memory_mb = info.get("used_memory", 0) / (1024 * 1024) if "used_memory" in info else None
        redis_version = info.get("redis_version")
        uptime_seconds = info.get("uptime_in_seconds")

        return CacheStatsResponse(
            total_keys=db_size,
            memory_usage_mb=round(memory_mb, 2) if memory_mb else None,
            redis_version=redis_version,
            uptime_seconds=uptime_seconds,
        )
    finally:
        await client.aclose()


@router.post("/cache/clear", response_model=DeleteResponse)
async def clear_cache(
    prefix: str | None = Query(default=None),
    _auth: None = Depends(verify_admin_key),
) -> DeleteResponse:
    """Clear cache entries (optionally by prefix).

    Args:
        prefix: Optional key prefix to match (e.g., 'embed:', 'yg-starter:chat:')
        _auth: Admin authentication

    Returns:
        DeleteResponse with number of deleted keys
    """
    logger.info("admin_clear_cache", prefix=prefix)

    client = await get_redis_client()

    try:
        if prefix:
            # Find keys matching prefix
            pattern = f"{prefix}*"
            keys = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)

            if keys:
                deleted = await client.delete(*keys)
            else:
                deleted = 0
        else:
            # Clear all keys (dangerous!)
            await client.flushdb()
            deleted = -1  # Unknown count

        logger.info("admin_cache_cleared", prefix=prefix, deleted=deleted)

        return DeleteResponse(
            deleted_count=deleted,
            message=f"Cleared {deleted if deleted >= 0 else 'all'} cache entries",
        )
    finally:
        await client.aclose()


@router.get("/cache/embedding-stats", response_model=dict)
async def embedding_cache_stats(
    _auth: None = Depends(verify_admin_key),
) -> dict:
    """Get embedding cache specific stats.

    Args:
        _auth: Admin authentication

    Returns:
        Dictionary with embedding cache statistics
    """
    logger.info("admin_embedding_cache_stats")

    client = await get_redis_client()

    try:
        # Count embedding cache keys (langchain-redis uses 'embed:' prefix)
        embed_keys = 0
        async for _ in client.scan_iter(match="embed:*", count=100):
            embed_keys += 1

        # Count chat history keys
        chat_keys = 0
        async for _ in client.scan_iter(match="yg-starter:chat:*", count=100):
            chat_keys += 1

        # Count semantic cache keys (vector index)
        semantic_keys = 0
        async for _ in client.scan_iter(match="semantic:*", count=100):
            semantic_keys += 1

        return {
            "embedding_cache_keys": embed_keys,
            "chat_history_keys": chat_keys,
            "semantic_cache_keys": semantic_keys,
            "total_tracked": embed_keys + chat_keys + semantic_keys,
        }
    finally:
        await client.aclose()


# --- System Info Endpoint ---


# Track application start time
_APP_START_TIME = time.time()


@router.get("/info", response_model=SystemInfoResponse)
async def system_info(
    _auth: None = Depends(verify_admin_key),
) -> SystemInfoResponse:
    """Get system information.

    Args:
        _auth: Admin authentication

    Returns:
        SystemInfoResponse with system details
    """
    logger.info("admin_system_info")

    uptime = time.time() - _APP_START_TIME

    return SystemInfoResponse(
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(uptime, 2),
        config={
            "llm_model": settings.LLM_MODEL,
            "llm_provider": settings.resolved_llm_provider(),
            "database_configured": bool(settings.DATABASE_URL),
            "redis_configured": bool(settings.REDIS_URL),
            "langfuse_enabled": settings.LANGFUSE_ENABLED,
        },
    )


# --- Usage Stats Endpoint ---


@router.get("/stats/usage")
async def get_usage_statistics(
    _auth: None = Depends(verify_admin_key),
) -> dict:
    """Get application usage statistics.

    Retrieves comprehensive usage stats including:
    - Chat request counts (total and daily)
    - Token usage (input/output)
    - Embedding statistics with cache hit rates
    - Memory recall operations

    Args:
        _auth: Admin authentication

    Returns:
        Dictionary with usage statistics grouped by category
    """
    logger.info("admin_usage_stats")

    stats = get_usage_stats()
    return await stats.get_stats()


@router.post("/stats/usage/reset")
async def reset_usage_statistics(
    _auth: None = Depends(verify_admin_key),
) -> dict:
    """Reset all usage statistics.

    WARNING: This will delete all tracked statistics. Use with caution.

    Args:
        _auth: Admin authentication

    Returns:
        Dictionary with count of deleted keys
    """
    logger.warning("admin_usage_stats_reset")

    stats = get_usage_stats()
    deleted = await stats.reset_stats()

    return {
        "status": "success",
        "keys_deleted": deleted,
        "message": f"Reset {deleted} usage statistics",
    }
