"""Health check endpoints."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Basic health check endpoint for load balancers and monitoring.

    Returns HTTP 200 if the service is running.
    """
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness check endpoint with dependency verification.

    Checks:
    - Database connectivity
    - Redis connectivity

    Returns HTTP 200 if ready, HTTP 503 if not ready.
    """
    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))

    # Check Redis
    try:
        redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis.ping()
        await redis.aclose()
        checks["redis"] = True
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))

    # Overall readiness
    is_ready = all(checks.values())

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        },
    )
