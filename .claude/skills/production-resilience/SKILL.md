# Production Resilience Patterns

**Master production-grade resilience for Python/FastAPI applications**

## Overview

Production resilience ensures your application survives failures gracefully. This skill covers circuit breakers, timeouts, graceful degradation, rate limiting, and caching patterns.

## Core Patterns

### 1. Circuit Breaker

Prevents cascading failures when external services fail.

```python
from pybreaker import CircuitBreaker
import structlog

logger = structlog.get_logger()

# Configure circuit breaker
external_api_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    reset_timeout=60,     # Try again after 60 seconds
    exclude=[ValueError]  # Don't count validation errors
)

@external_api_breaker
async def call_external_api(data: dict) -> dict:
    """Call external API with circuit breaker protection."""
    async with timeout(10.0):
        response = await client.post("/api", json=data)
        response.raise_for_status()
        return response.json()

# Usage with fallback
async def get_data_with_fallback(data: dict) -> dict:
    try:
        return await call_external_api(data)
    except CircuitBreakerError:
        logger.warning("circuit_open", service="external_api")
        return {"fallback": True, "data": None}
```

### 2. Request Timeouts

Every async external call MUST have a timeout.

```python
from asyncio import timeout, TimeoutError

# ❌ BAD: No timeout - can block forever
result = await external_service.call()

# ✅ GOOD: Timeout protection
async with timeout(30.0):
    result = await external_service.call()

# ✅ BETTER: Timeout with graceful handling
async def safe_call(query: str) -> str:
    try:
        async with timeout(5.0):
            return await memory_service.recall(query)
    except TimeoutError:
        logger.warning("operation_timeout", operation="memory_recall")
        return ""  # Return empty, don't fail request
```

### 3. Graceful Degradation

Non-critical features should fail open, not crash the request.

```python
async def chat(request: ChatRequest) -> ChatResponse:
    # Critical: Must succeed
    agent = get_agent()

    # Non-critical: Can fail gracefully
    proactive_context = ""
    try:
        async with timeout(2.0):
            proactive_context = await memory_service.proactive_recall(
                request.message
            )
    except Exception as e:
        logger.warning("memory_recall_failed", error=str(e))
        # Continue without memory - degraded but functional

    # Continue with request
    result = await agent.ainvoke({
        "query": request.message,
        "context": proactive_context,
    })
    return ChatResponse(response=result["response"])
```

### 4. Rate Limiting

Protect endpoints from abuse.

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# Add to FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    """Chat endpoint with rate limiting."""
    ...

@app.post("/api/embed")
@limiter.limit("100/minute")  # Higher limit for embeddings
async def embed(request: Request, body: EmbedRequest):
    ...
```

### 5. Connection Pooling

Configure database connection pools to prevent exhaustion.

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Base pool size
    max_overflow=10,       # Allow 10 extra connections during spikes
    pool_pre_ping=True,    # Check connection health before use
    pool_recycle=3600,     # Recycle connections every hour
    pool_timeout=30,       # Wait max 30s for connection
    echo_pool=True,        # Log pool events (disable in prod)
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

### 6. Redis Caching

Cache expensive operations.

```python
import hashlib
import json
from redis.asyncio import Redis

class CacheService:
    def __init__(self, redis: Redis, default_ttl: int = 3600):
        self.redis = redis
        self.default_ttl = default_ttl

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int | None = None
    ) -> T:
        """Get from cache or compute and cache."""
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        result = await factory()
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(result)
        )
        return result

# Usage for embeddings
async def get_cached_embedding(text: str) -> list[float]:
    cache_key = f"embed:{hashlib.sha256(text.encode()).hexdigest()}"
    return await cache.get_or_set(
        cache_key,
        lambda: embedding_service.generate(text),
        ttl=86400  # 24 hours
    )
```

### 7. Health Checks

Provide health and readiness endpoints.

```python
from fastapi import FastAPI, Response
from sqlalchemy import text

@app.get("/health")
async def health():
    """Basic health check - is the service running?"""
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    """Readiness check - are all dependencies available?"""
    checks = {}

    # Database
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return Response(
        content=json.dumps({"ready": all_ok, "checks": checks}),
        status_code=200 if all_ok else 503,
        media_type="application/json"
    )
```

## Implementation Checklist

### Critical (Must Have)
- [ ] Timeouts on all external calls (<30s default, <5s for non-critical)
- [ ] Circuit breakers on external services
- [ ] Rate limiting on public endpoints
- [ ] Connection pooling for databases
- [ ] Graceful degradation for non-critical features

### High Priority
- [ ] Redis caching for expensive operations
- [ ] Health check endpoints (/health, /ready)
- [ ] Structured logging with correlation IDs
- [ ] Retry with exponential backoff

### Nice to Have
- [ ] Request coalescing for duplicate concurrent requests
- [ ] Bulkhead pattern for resource isolation
- [ ] Fallback services for critical paths

## Dependencies

```toml
# pyproject.toml
[project.dependencies]
pybreaker = "^1.0.0"
slowapi = "^0.1.9"
redis = "^5.0.0"
structlog = "^24.0.0"
```

## Testing Resilience

```python
import pytest
from unittest.mock import AsyncMock, patch
from pybreaker import CircuitBreakerError

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after max failures."""
    with patch("service.external_call") as mock:
        mock.side_effect = Exception("Service down")

        # Fail 5 times to open circuit
        for _ in range(5):
            with pytest.raises(Exception):
                await call_with_breaker()

        # Next call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await call_with_breaker()

@pytest.mark.asyncio
async def test_graceful_degradation():
    """Test service continues when non-critical feature fails."""
    with patch("service.memory_recall") as mock:
        mock.side_effect = TimeoutError()

        # Should not raise, should return degraded response
        result = await chat(ChatRequest(message="Hello"))

        assert result.response is not None
        # Context should be empty due to timeout
```

---

**Version:** 1.0.0 (December 2025)
**Related Skills:** context-engineering, performance-optimization
