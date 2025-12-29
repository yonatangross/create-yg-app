# Real-World API Design Example

Production-ready API design for a content analysis service with FastAPI + SQLAlchemy 2.0, demonstrating 2025 best practices.

## Service Context

**Service**: Content Analysis API - Multi-agent system for analyzing technical content
**Stack**: FastAPI + PostgreSQL + pgvector + Redis
**Base URL**: `https://api.example.com/v1`

**Development Ports**:
- Backend API: `localhost:8600`
- Frontend: `localhost:5183`
- PostgreSQL: `localhost:5447`

## API Structure

### URI Versioning

**Decision**: Use URI-based versioning (`/api/v1/`)

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Content Analysis API"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Implementation**: `backend/app/main.py`
```python
from fastapi import FastAPI
from app.api.v1 import analysis, artifacts
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

# Include routers with versioned prefix
app.include_router(
    analysis.router,
    prefix=f"{settings.API_V1_PREFIX}/analyze",
    tags=["analysis"]
)

app.include_router(
    artifacts.router,
    prefix=settings.API_V1_PREFIX,
    tags=["artifacts"]
)
```

## Endpoint Design

### 1. Create Analysis (Async Task Pattern)

```python
# POST /api/v1/analyze
from pydantic import BaseModel, HttpUrl, Field
from typing import Literal

class AnalyzeRequest(BaseModel):
    url: HttpUrl
    analysis_id: str | None = None
    skill_level: Literal["beginner", "intermediate", "advanced"] = "beginner"

class AnalyzeCreateResponse(BaseModel):
    analysis_id: str
    url: str
    content_type: str
    status: Literal["pending", "processing", "complete", "failed"]
    sse_endpoint: str  # For progress streaming

@router.post(
    "/analyze",
    status_code=status.HTTP_201_CREATED,
    response_model=AnalyzeCreateResponse
)
async def create_analysis(
    request: AnalyzeRequest,
    fastapi_request: Request,
    session: AsyncSession = Depends(get_session)
) -> AnalyzeCreateResponse:
    """Create analysis and start workflow asynchronously."""

    # Generate UUID
    analysis_uuid = uuid.uuid4() if not request.analysis_id else uuid.UUID(request.analysis_id)

    # Detect content type
    content_type = await detect_content_type(str(request.url))

    # Create database record
    analysis = Analysis(
        id=analysis_uuid,
        url=str(request.url),
        content_type=content_type,
        status="pending"
    )
    session.add(analysis)
    await session.commit()

    # Start workflow asynchronously (fire-and-forget)
    asyncio.create_task(
        run_analysis_workflow(analysis_uuid, str(request.url), request.skill_level)
    )

    # Return immediately with SSE endpoint
    return AnalyzeCreateResponse(
        analysis_id=str(analysis_uuid),
        url=str(request.url),
        content_type=content_type,
        status="pending",
        sse_endpoint=f"{settings.API_V1_PREFIX}/analyze/{analysis_uuid}/stream"
    )
```

**Design Decision**: Return immediately with analysis_id + SSE endpoint
- **Why**: Analysis workflow takes 30-120 seconds
- **Pattern**: Async task creation + progress streaming
- **Client flow**: Create analysis → Connect to SSE → Receive progress

### 2. Get Analysis Status

```python
# GET /api/v1/analyze/{analysis_id}
from sqlalchemy import select

class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    url: str
    content_type: str
    status: str
    title: str | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime

@router.get(
    "/analyze/{analysis_id}",
    response_model=AnalysisStatusResponse
)
async def get_analysis(
    analysis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session)
) -> AnalysisStatusResponse:
    """Get analysis status and results."""

    # Query with relationship loading
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    result = await session.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id} not found"
        )

    return AnalysisStatusResponse(
        analysis_id=str(analysis.id),
        url=analysis.url,
        content_type=analysis.content_type,
        status=analysis.status,
        title=analysis.title,
        artifact_id=str(analysis.latest_artifact_id) if analysis.latest_artifact_id else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at
    )
```

### 3. Stream Progress (Server-Sent Events)

```python
# GET /api/v1/analyze/{analysis_id}/stream
from sse_starlette.sse import EventSourceResponse
from contextlib import aclosing

@router.get("/analyze/{analysis_id}/stream")
async def stream_analysis_progress(
    analysis_id: uuid.UUID,
    request: Request
) -> EventSourceResponse:
    """Stream real-time progress via SSE."""

    channel = f"workflow:{analysis_id}"

    async def event_generator():
        try:
            async with aclosing(broadcaster.subscribe(channel)) as subscription:
                async for event in subscription:
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event)
                    }

                    if event.get("type") == "complete":
                        break
        except asyncio.CancelledError:
            logger.info("SSE connection cancelled", analysis_id=str(analysis_id))
            raise

    return EventSourceResponse(
        event_generator(),
        send_timeout=30.0
    )
```

### 4. Get Artifact

```python
# GET /api/v1/artifacts/{artifact_id}
class ArtifactResponse(BaseModel):
    artifact_id: str
    analysis_id: str
    markdown_content: str
    metadata: dict = {}
    created_at: datetime

@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactResponse
)
async def get_artifact(
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session)
) -> ArtifactResponse:
    """Get artifact by ID."""

    stmt = select(Artifact).where(Artifact.id == artifact_id)
    result = await session.execute(stmt)
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return ArtifactResponse(
        artifact_id=str(artifact.id),
        analysis_id=str(artifact.analysis_id),
        markdown_content=artifact.markdown_content,
        metadata=artifact.metadata or {},
        created_at=artifact.created_at
    )
```

### 5. Download Artifact

```python
# GET /api/v1/artifacts/{artifact_id}/download
from fastapi.responses import Response

@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session)
) -> Response:
    """Download artifact as markdown file."""

    # Get artifact with analysis (for title)
    stmt = select(Artifact, Analysis).join(
        Analysis, Artifact.analysis_id == Analysis.id
    ).where(Artifact.id == artifact_id)

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact, analysis = row

    # Generate filename
    title_slug = analysis.title.lower().replace(" ", "-")[:50] if analysis.title else "analysis"
    filename = f"{title_slug}-{str(artifact_id)[:8]}.md"

    # Increment download counter (fire and forget)
    asyncio.create_task(increment_download_count(artifact_id, session))

    return Response(
        content=artifact.markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
```

## Error Handling

### Standardized Error Format

```python
# backend/app/api/schemas/errors.py
from pydantic import BaseModel
from datetime import datetime

class ErrorDetail(BaseModel):
    field: str
    message: str
    code: str

class ErrorResponse(BaseModel):
    error: dict

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [
                        {
                            "field": "url",
                            "message": "Invalid URL format",
                            "code": "INVALID_URL"
                        }
                    ],
                    "timestamp": "December 2025T10:30:00Z",
                    "request_id": "req_abc123"
                }
            }
        }
    }
```

### Global Exception Handler

```python
# backend/app/main.py
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime, UTC

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "code": error["type"]
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors,
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request.state.request_id
            }
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR",
                "message": str(exc.detail),
                "timestamp": datetime.now(UTC).isoformat(),
                "request_id": request.state.request_id
            }
        }
    )
```

## Database Models (SQLAlchemy 2.0)

```python
# backend/app/models/analysis.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, func
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan"
    )

class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[dict | None] = mapped_column(JSONB)
    download_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    analysis: Mapped["Analysis"] = relationship(back_populates="artifacts")
```

## Health Check Endpoint

```python
# GET /api/v1/health
from sqlalchemy import text

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: dict

@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_session)
) -> HealthResponse:
    """Health check with database connectivity."""

    db_status = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        db_status = "disconnected"

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        database={"status": db_status}
    )
```

## Design Principles Applied

### 1. Async/Await Everywhere
- All database operations use `AsyncSession`
- All I/O operations are async
- Background tasks with `asyncio.create_task()`

### 2. SQLAlchemy 2.0 Patterns
- `Mapped` types for type safety
- `select()` statements instead of Query API
- Relationship loading with explicit joins

### 3. Pydantic v2
- `BaseModel` with `model_config`
- Field validation with `Field()`
- Type hints with `|` instead of `Optional`

### 4. Immediate Response + Progress Streaming
- Return 201 Created immediately
- Provide SSE endpoint for progress
- Client doesn't wait for long operation

### 5. Hierarchical URLs
- `/analyze/{id}/artifact` - Clear relationship
- `/analyze/{id}/stream` - Progress for specific analysis

## Testing Examples

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_analysis(client: AsyncClient):
    response = await client.post(
        "/api/v1/analyze",
        json={
            "url": "https://example.com/article",
            "skill_level": "beginner"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert "analysis_id" in data
    assert "sse_endpoint" in data
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_get_nonexistent_analysis(client: AsyncClient):
    response = await client.get(
        f"/api/v1/analyze/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
```

## OpenAPI Documentation

FastAPI auto-generates OpenAPI docs at:
- Swagger UI: `http://localhost:8600/docs`
- ReDoc: `http://localhost:8600/redoc`
- OpenAPI JSON: `http://localhost:8600/api/v1/openapi.json`

---

**Example Version**: 1.0.0
**Last Updated**: December 2025
**Stack**: FastAPI 0.115+ | SQLAlchemy 2.0 | Pydantic v2 | PostgreSQL 16
