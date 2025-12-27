"""Chat endpoint with SSE streaming."""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import get_agent
from app.core.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = Field(default=None)


class ChatResponse(BaseModel):
    """Response body for non-streaming chat."""

    response: str
    conversation_id: str


@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message and get a response (non-streaming)."""
    agent = get_agent()

    result = await agent.ainvoke(
        {
            "query": request.message,
            "conversation_id": request.conversation_id or "default",
        }
    )

    return ChatResponse(
        response=result.get("response", ""),
        conversation_id=result.get("conversation_id", "default"),
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Send a message and stream the response via SSE."""

    async def event_generator() -> AsyncGenerator[dict, None]:
        agent = get_agent()

        try:
            async for event in agent.astream_events(
                {
                    "query": request.message,
                    "conversation_id": request.conversation_id or "default",
                },
                version="v2",
            ):
                # Check if client disconnected
                if await req.is_disconnected():
                    logger.info("client_disconnected")
                    break

                event_type = event.get("event")

                # Stream tokens from the LLM
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {
                            "event": "token",
                            "data": chunk.content,
                        }

                # Stream workflow events
                elif event_type == "on_chain_end":
                    name = event.get("name", "")
                    if name == "agent":
                        output = event.get("data", {}).get("output", {})
                        if response := output.get("response"):
                            yield {
                                "event": "complete",
                                "data": response,
                            }

        except asyncio.CancelledError:
            logger.info("stream_cancelled")
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield {
                "event": "error",
                "data": str(e),
            }

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
