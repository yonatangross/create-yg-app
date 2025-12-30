# Circuit Breaker Implementation

## Overview

Added circuit breaker protection to the `EmbeddingService` to prevent cascade failures when the OpenAI API is unavailable or experiencing issues. This implements a fail-fast pattern that protects the system from repeatedly calling a failing service.

## Implementation Details

### 1. Circuit Breaker Module

**File**: `/Users/yonatangross/coding/create-yg-app/backend/app/core/circuit_breaker.py`

Provides pre-configured circuit breakers for different external services:

- **openai_breaker**: Protects OpenAI API calls (embeddings)
  - Failure threshold: 5 failures
  - Success threshold: 2 successes to close
  - Timeout: 60 seconds

- **llm_breaker**: Protects LLM inference calls (agent operations)
  - Failure threshold: 3 failures
  - Success threshold: 2 successes to close
  - Timeout: 120 seconds

- **db_query_breaker**: Protects database heavy queries
  - Failure threshold: 10 failures
  - Success threshold: 3 successes to close
  - Timeout: 30 seconds

### 2. EmbeddingService Integration

**File**: `/Users/yonatangross/coding/create-yg-app/backend/app/shared/services/memory/embedding_service.py`

Protected methods:
- `generate_embedding()` - Single embedding generation
- `generate_embeddings_batch()` - Batch embedding generation

#### Pattern Used

```python
async def generate_embedding(self, text: str) -> EmbeddingVector:
    """Public method with circuit breaker protection."""
    try:
        return await openai_breaker.call(self._generate_embedding_internal, text)
    except CircuitBreakerOpenError:
        logger.error("openai_circuit_open", text_length=len(text))
        raise

@retry(...)
async def _generate_embedding_internal(self, text: str) -> EmbeddingVector:
    """Internal method with retry logic."""
    # Actual OpenAI API call
```

**Benefits**:
1. Circuit breaker wraps the entire retry mechanism
2. Retries (3 attempts) happen first before circuit opens
3. After 5 failed operations (each with 3 retries), circuit opens
4. Provides fast failure without waiting for timeouts

### 3. Circuit Breaker States

```
CLOSED (Normal) → OPEN (Fast Fail) → HALF_OPEN (Testing) → CLOSED
     ↑                                                           |
     └───────────────────────────────────────────────────────────┘
```

**State Transitions**:
- CLOSED → OPEN: After 5 consecutive failures
- OPEN → HALF_OPEN: After 60-second timeout
- HALF_OPEN → CLOSED: After 2 consecutive successes
- HALF_OPEN → OPEN: After any failure

### 4. Logging

Circuit breaker events are logged using structlog:

```python
logger.warning("circuit_breaker_opened", name="openai_api", threshold=5)
logger.info("circuit_breaker_half_open", name="openai_api", elapsed_seconds=60)
logger.info("circuit_breaker_closed", name="openai_api")
logger.error("openai_circuit_open", text_length=100)
```

## Testing

**File**: `/Users/yonatangross/coding/create-yg-app/backend/tests/unit/test_embedding_service.py`

Added comprehensive circuit breaker tests:

1. `test_circuit_breaker_opens_after_failures` - Verifies circuit opens after 5 failures
2. `test_circuit_breaker_allows_requests_when_closed` - Normal operation when closed
3. `test_circuit_breaker_resets_after_success` - Failure count resets on success
4. `test_circuit_breaker_with_batch_embeddings` - Batch operations protected
5. `test_circuit_breaker_excludes_value_errors` - ValueError doesn't trigger circuit
6. `test_circuit_breaker_logs_open_state` - Logging verification

**Test Results**: All 50 tests pass (6 new circuit breaker tests added)

```bash
uv run pytest tests/unit/test_embedding_service.py -v
# 50 passed in 119.89s
```

## Usage Example

```python
from app.shared.services.memory.embedding_service import get_embedding_service
from app.core.resilience import CircuitBreakerOpenError

service = get_embedding_service()

try:
    embedding = await service.generate_embedding("Hello, world!")
except CircuitBreakerOpenError:
    # OpenAI API is down, fail fast
    logger.error("embedding_service_unavailable")
    # Implement fallback logic or return cached result
```

## Dependencies

**Note**: The implementation uses the existing `app.core.resilience` module instead of adding `pybreaker` as a dependency. This provides:

- Async/await native support (pybreaker is synchronous)
- Better integration with existing codebase
- TypeScript-like type hints
- Structlog integration

## Performance Impact

**Before**:
- Failed requests wait for full timeout + 3 retries
- Total wait time: ~90+ seconds per failed request

**After**:
- First 5 failures: Normal retry behavior (~90s total)
- Subsequent failures: Instant rejection (<1ms)
- Recovery attempt: After 60 seconds in half-open state

**Savings**: 99%+ reduction in latency for requests when circuit is open

## Production Considerations

1. **Monitoring**: Track circuit breaker state changes in production logs
2. **Alerts**: Set up alerts for circuit opening (indicates service degradation)
3. **Fallbacks**: Implement fallback strategies when circuit is open
4. **Manual Reset**: Circuit breaker can be manually reset via `openai_breaker.reset()`

## Future Enhancements

1. Add circuit breaker metrics to Langfuse tracing
2. Expose circuit breaker state via health check endpoint
3. Implement adaptive thresholds based on historical data
4. Add circuit breaker to other external service calls (Anthropic, Google AI)

## References

- Custom Circuit Breaker: `/Users/yonatangross/coding/create-yg-app/backend/app/core/resilience.py`
- Architecture Doc: `/Users/yonatangross/coding/create-yg-app/docs/ARCHITECTURE.md` (Section 3.3)
- Production Resilience Skill: `.claude/skills/production-resilience/`
