"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness check endpoint.

    Verifies the application is ready to serve requests.
    """
    # TODO: Add database and Redis connectivity checks
    return {"status": "ready"}
