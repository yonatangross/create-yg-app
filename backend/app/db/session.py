"""Database session management for async SQLAlchemy."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Get cached async database engine with optimized connection pooling.

    Returns:
        Configured AsyncEngine with production-ready connection pooling.

    Pool Configuration:
        - pool_size=20: Base connection pool size (increased from 5 for better concurrency)
        - max_overflow=10: Additional connections allowed during peak load
        - pool_pre_ping=True: Validates connections before use (prevents stale connections)
        - pool_recycle=3600: Recycle connections every hour (prevents long-lived connection issues)
    """
    if not settings.DATABASE_URL:
        msg = "DATABASE_URL is not configured"
        raise ValueError(msg)

    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development(),
        pool_pre_ping=True,
        pool_size=20,  # Increased for better concurrency
        max_overflow=10,
        pool_recycle=3600,  # Recycle connections every hour
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get cached session factory.

    Returns:
        Configured async_sessionmaker for creating sessions.
    """
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    Yields:
        AsyncSession with automatic cleanup.

    Example:
        async with get_session() as session:
            result = await session.execute(select(Model))
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession for request handling.

    Usage in FastAPI:
        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_session() as session:
        yield session


async def set_statement_timeout(session: AsyncSession, timeout_ms: int) -> None:
    """Set statement timeout for the current session.

    Args:
        session: The database session.
        timeout_ms: Timeout in milliseconds.

    Usage:
        async with get_session() as session:
            await set_statement_timeout(session, 5000)  # 5 second timeout
            result = await session.execute(stmt)
    """
    await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
