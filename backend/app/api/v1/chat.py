"""Chat endpoint with SSE streaming."""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import get_agent
from app.core.logging import get_logger
from app.db.session import get_session
from app.shared.services.cache.redis_service import get_chat_history
from app.shared.services.memory import MemoryService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)

# Maximum messages to keep in Redis sliding window
MAX_CONTEXT_MESSAGES = 20


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
    conversation_id = request.conversation_id or "default"

    # 1. LOAD SHORT-TERM MEMORY (Redis)
    chat_history = get_chat_history(conversation_id)
    messages = await chat_history.aget_messages()

    # Apply sliding window: keep only last MAX_CONTEXT_MESSAGES
    if len(messages) > MAX_CONTEXT_MESSAGES:
        messages = messages[-MAX_CONTEXT_MESSAGES:]
        logger.debug(
            "sliding_window_applied",
            conversation_id=conversation_id,
            kept_messages=len(messages),
        )

    # 2. LOAD LONG-TERM MEMORY (PostgreSQL)
    proactive_context = ""
    async with get_session() as session:
        memory_service = MemoryService(session)
        proactive_context = await memory_service.proactive_recall(request.message)

    # 3. INVOKE AGENT
    agent = get_agent()
    result = await agent.ainvoke(
        {
            "query": request.message,
            "conversation_id": conversation_id,
            "messages": messages,
            "proactive_context": proactive_context,
        }
    )

    # 4. SAVE SHORT-TERM MEMORY (Redis)
    response_text = result.get("response", "")
    await chat_history.aadd_messages(
        [
            HumanMessage(content=request.message),
            AIMessage(content=response_text),
        ]
    )

    logger.info(
        "chat_completed",
        conversation_id=conversation_id,
        message_length=len(request.message),
        response_length=len(response_text),
        has_proactive_context=bool(proactive_context),
    )

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Send a message and stream the response via SSE."""
    conversation_id = request.conversation_id or "default"

    # 1. LOAD SHORT-TERM MEMORY (Redis)
    chat_history = get_chat_history(conversation_id)
    messages = await chat_history.aget_messages()

    # Apply sliding window: keep only last MAX_CONTEXT_MESSAGES
    if len(messages) > MAX_CONTEXT_MESSAGES:
        messages = messages[-MAX_CONTEXT_MESSAGES:]
        logger.debug(
            "sliding_window_applied",
            conversation_id=conversation_id,
            kept_messages=len(messages),
        )

    # 2. LOAD LONG-TERM MEMORY (PostgreSQL)
    proactive_context = ""
    async with get_session() as session:
        memory_service = MemoryService(session)
        proactive_context = await memory_service.proactive_recall(request.message)

    async def event_generator() -> AsyncGenerator[dict, None]:
        agent = get_agent()
        accumulated_response = []

        try:
            async for event in agent.astream_events(
                {
                    "query": request.message,
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "proactive_context": proactive_context,
                },
                version="v2",
            ):
                # Check if client disconnected
                if await req.is_disconnected():
                    logger.info("client_disconnected")
                    break

                event_type = event.get("event")

                # Stream tokens from the LLM and accumulate
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        accumulated_response.append(chunk.content)
                        yield {
                            "event": "token",
                            "data": chunk.content,
                        }

            # Stream completed - save to Redis
            if accumulated_response:
                full_response = "".join(accumulated_response)
                yield {
                    "event": "complete",
                    "data": full_response,
                }

                # 3. SAVE SHORT-TERM MEMORY (Redis) - after stream completes
                await chat_history.aadd_messages(
                    [
                        HumanMessage(content=request.message),
                        AIMessage(content=full_response),
                    ]
                )

                logger.info(
                    "chat_stream_completed",
                    conversation_id=conversation_id,
                    message_length=len(request.message),
                    response_length=len(full_response),
                    has_proactive_context=bool(proactive_context),
                )

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
